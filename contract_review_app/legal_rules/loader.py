# contract_review_app/legal_rules/loader.py
"""YAML rule loader for policy and core rule packs."""

from __future__ import annotations

import contextvars
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

# Новая нормализация при intake: кавычки/дефисы -> ASCII, сжатие пробелов, сохранение \n
from ..intake.normalization import normalize_for_intake

log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Rule roots and extension filter
# ---------------------------------------------------------------------------

RULE_ROOTS = [
    "contract_review_app/legal_rules",
    "core/rules",
]
ALLOWED_RULE_EXTS = {".yml", ".yaml"}

# Global meta information used by tests/diagnostics
meta: Dict[str, Any] = {"debug": {}}

# Priority mapping for packs defined in core/rules/registry.yml
REGISTRY_FILE = ROOT_DIR / "core/rules" / "registry.yml"
BASELINE_FILE = Path(__file__).resolve().with_name("baseline_patterns.yaml")
PACK_PRIORITIES: Dict[str, int] = {}
if REGISTRY_FILE.exists():
    try:
        _reg_data = yaml.safe_load(REGISTRY_FILE.read_text(encoding="utf-8")) or {}
        for _doc, juris in _reg_data.items():
            for _juris, packs in (juris or {}).items():
                for idx, p in enumerate(packs or []):
                    PACK_PRIORITIES.setdefault(str(p), idx)
    except Exception:  # pragma: no cover
        PACK_PRIORITIES = {}

_ENV_DIRS = os.getenv("RULE_PACKS_DIRS")
if _ENV_DIRS:
    RULE_ROOTS = [p.strip() for p in _ENV_DIRS.split(os.pathsep) if p.strip()]


def _resolve_root(p: str | Path) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


_RULES: List[Dict[str, Any]] = []
_PACKS: List[Dict[str, Any]] = []
CANDIDATES_VAR: contextvars.ContextVar[Optional[Set[str]]] = contextvars.ContextVar(
    "candidate_rule_ids", default=None
)


@dataclass
class RuleMeta:
    path: str
    sha256: str
    title: Optional[str] = None
    pack: Optional[str] = None
    priority: int = 0


PICKED: Dict[str, Tuple[int, RuleMeta, int]] = {}
SHADOWED: Dict[str, List[RuleMeta]] = {}

# ---------------------------------------------------------------------------
# Coverage flags (bitmask)
# ---------------------------------------------------------------------------
SCHEMA_MISMATCH = 1 << 0
DOC_TYPE_MISMATCH = 1 << 1
JURISDICTION_MISMATCH = 1 << 2
NO_CLAUSE = 1 << 3
REGEX_MISS = 1 << 4
WHEN_FALSE = 1 << 5
TEXT_NORMALIZATION_ISSUE = 1 << 6
FIRED = 1 << 7


def _compile(patterns: Iterable[str]) -> List[re.Pattern[str]]:
    """Compile regex patterns with IGNORECASE|MULTILINE by default (inline flags respected)."""
    return [re.compile(p, re.I | re.MULTILINE) for p in patterns if p]


class RuleSchema(BaseModel):
    """Pydantic model validating the unified rule specification."""

    rule_id: str = Field(alias="id")
    doc_types: List[str] = Field(default_factory=list)
    jurisdiction: List[str] = Field(default_factory=list)
    severity: str = Field(default="medium")
    triggers: Dict[str, List[str]] = Field(default_factory=dict)
    requires_clause: List[str] = Field(default_factory=list)
    advice: Optional[str] = None
    law_refs: List[Any] = Field(default_factory=list)
    deprecated: bool = False

    @field_validator("severity")
    @classmethod
    def _severity_valid(cls, v: str) -> str:
        val = str(v or "").lower()
        if val not in {"high", "medium", "low"}:
            raise ValueError("invalid severity")
        return val


def load_rule_packs(roots: Iterable[str | Path] | None = None) -> None:
    """Load YAML rule packs from configured directories with deduplication."""
    _RULES.clear()
    _PACKS.clear()
    PICKED.clear()
    SHADOWED.clear()
    meta.setdefault("debug", {})
    meta["debug"].setdefault("duplicates", {})
    meta["debug"]["duplicates"] = {}
    base_dirs = [_resolve_root(p) for p in (roots or RULE_ROOTS)]

    for base in base_dirs:
        if not base.exists():
            continue

        paths = sorted(p for p in base.rglob("*") if p.is_file())
        for path in paths:
            if any(part == ".venv" for part in path.parts):
                continue
            if "_legacy_disabled" in path.parts:
                continue
            if path.suffix.lower() not in ALLOWED_RULE_EXTS:
                continue
            if path.resolve() == REGISTRY_FILE.resolve():
                continue
            if path.resolve() == BASELINE_FILE.resolve():
                continue
            try:
                docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            except Exception as exc:  # pragma: no cover
                log.error("Failed to load %s: %s", path, exc)
                continue

            file_sha = hashlib.sha256(path.read_bytes()).hexdigest()

            # Pack identifier and priority
            try:
                pack_rel_core = path.relative_to(ROOT_DIR / "core/rules")
                pack_id = pack_rel_core.parent.as_posix()
            except ValueError:
                try:
                    pack_id = path.parent.relative_to(ROOT_DIR).as_posix()
                except ValueError:  # pragma: no cover
                    pack_id = path.parent.as_posix()
            priority = PACK_PRIORITIES.get(pack_id, 10_000)

            rule_count = 0
            for data in docs:
                if not data:
                    continue

                if isinstance(data, dict) and data.get("rule"):
                    rules_iter: List[Dict[str, Any]] = [data["rule"]]
                elif isinstance(data, dict) and data.get("rules"):
                    rules_iter = list(data.get("rules") or [])
                elif isinstance(data, dict):
                    rules_iter = [data]
                elif isinstance(data, list):
                    rules_iter = list(data)
                else:
                    rules_iter = []

                for raw in rules_iter:
                    rid = raw.get("rule_id") or raw.get("id")
                    if not rid:
                        log.warning("Rule without rule_id: %s", path)
                        continue

                    # Собираем «плоский» список pat'ов из triggers.{any,all,regex}/patterns
                    pats: List[str] = []
                    trig_any = raw.get("triggers", {}).get("any", []) or []
                    trig_all = raw.get("triggers", {}).get("all", []) or []
                    trig_regex = raw.get("triggers", {}).get("regex", []) or []

                    if raw.get("patterns"):
                        pats = list(raw.get("patterns", []))
                    else:

                        def _pull(xs):
                            for c in xs:
                                yield c.get("regex") if isinstance(c, dict) else c

                        pats.extend([p for p in _pull(trig_any) if p])
                        pats.extend([p for p in _pull(trig_all) if p])
                        pats.extend([p for p in _pull(trig_regex) if p])

                    finding_section = raw.get("finding")
                    if not finding_section:
                        checks = raw.get("checks") or []
                        if isinstance(checks, list):
                            for chk in checks:
                                if isinstance(chk, dict) and chk.get("finding"):
                                    finding_section = chk.get("finding")
                                    break

                    compiled_patterns = _compile(pats)

                    trig_map: Dict[str, List[re.Pattern[str]]] = {}
                    if trig_any:
                        trig_map["any"] = _compile(
                            [
                                (c.get("regex") if isinstance(c, dict) else c)
                                for c in trig_any
                            ]
                        )
                    if trig_all:
                        trig_map["all"] = _compile(
                            [
                                (c.get("regex") if isinstance(c, dict) else c)
                                for c in trig_all
                            ]
                        )
                    if trig_regex or raw.get("patterns"):
                        trig_map["regex"] = _compile(
                            [
                                (c.get("regex") if isinstance(c, dict) else c)
                                for c in (trig_regex or raw.get("patterns", []))
                            ]
                        )

                    doc_types = list(
                        raw.get("doc_types")
                        or (raw.get("scope", {}) or {}).get("doc_types")
                        or []
                    )
                    if doc_types:
                        dt_lc = [str(d).lower() for d in doc_types]
                        if "any" in dt_lc and len(dt_lc) > 1:
                            log.warning(
                                "Rule %s mixes 'Any' with specific doc_types %s",
                                rid,
                                doc_types,
                            )
                    jurisdiction = list(
                        raw.get("jurisdiction")
                        or (raw.get("scope", {}) or {}).get("jurisdiction")
                        or []
                    )
                    requires_clause = list(
                        raw.get("requires_clause")
                        or (raw.get("scope", {}) or {}).get("clauses")
                        or []
                    )
                    deprecated = bool(raw.get("deprecated"))

                    try:
                        pack_rel = str(path.relative_to(ROOT_DIR))
                    except ValueError:  # pragma: no cover
                        pack_rel = str(path)

                    title_val = raw.get("Title") or raw.get("title")
                    spec = {
                        "id": rid,
                        "rule_id": rid,
                        "Title": raw.get("Title"),
                        "title": title_val,
                        "clause_type": raw.get("clause_type")
                        or (raw.get("scope", {}) or {}).get("clauses", [None])[0],
                        "severity": str(
                            raw.get("severity")
                            or raw.get("risk")
                            or raw.get("severity_level")
                            or "medium"
                        ).lower(),
                        "patterns": compiled_patterns,
                        "advice": raw.get("advice")
                        or raw.get("intent")
                        or (finding_section or {}).get("suggestion", {}).get("text")
                        or (finding_section or {}).get("message"),
                        "law_refs": list(
                            raw.get("law_reference")
                            or raw.get("law_refs")
                            or (finding_section or {}).get("legal_basis")
                            or []
                        ),
                        "suggestion": (finding_section or {}).get("suggestion"),
                        "conflict_with": list(raw.get("conflict_with") or []),
                        "ops": raw.get("ops") or [],
                        "pack": pack_rel,
                        "triggers": trig_map,
                        "requires_clause_hit": bool(raw.get("requires_clause_hit")),
                        "doc_types": doc_types,
                        "jurisdiction": jurisdiction,
                        "requires_clause": requires_clause,
                        "deprecated": deprecated,
                    }

                    # Валидация схемы правила (но не прерываем загрузку)
                    try:
                        RuleSchema.model_validate(
                            {
                                "id": spec["id"],
                                "doc_types": doc_types,
                                "jurisdiction": jurisdiction,
                                "severity": spec["severity"],
                                "triggers": {
                                    k: [p.pattern for p in trig_map.get(k, [])]
                                    for k in trig_map.keys()
                                },
                                "requires_clause": requires_clause,
                                "advice": spec["advice"],
                                "law_refs": spec["law_refs"],
                                "deprecated": deprecated,
                            }
                        )
                    except ValidationError:
                        pass

                    rid = spec.get("id")
                    meta_obj = RuleMeta(
                        path=str(path),
                        sha256=file_sha,
                        title=title_val,
                        pack=pack_id,
                        priority=priority,
                    )
                    prev = PICKED.get(rid)
                    if prev is not None:
                        prev_pri, prev_meta, idx = prev
                        if priority < prev_pri:
                            SHADOWED.setdefault(rid, []).append(prev_meta)
                            PICKED[rid] = (priority, meta_obj, idx)
                            _RULES[idx] = spec
                        else:
                            SHADOWED.setdefault(rid, []).append(meta_obj)
                        continue
                    PICKED[rid] = (priority, meta_obj, len(_RULES))
                    _RULES.append(spec)
                    rule_count += 1

            try:
                rel = path.relative_to(ROOT_DIR)
            except ValueError:  # pragma: no cover
                rel = path
            _PACKS.append({"path": str(rel), "rule_count": rule_count})
    if SHADOWED:
        ids = list(SHADOWED.keys())
        log.warning(
            "Shadowed %d rule ids: %s",
            len(ids),
            ", ".join(ids[:20]),
        )
    meta["debug"]["duplicates"] = {
        rid: [m.path for m in metas] for rid, metas in SHADOWED.items()
    }

    # Remove deprecated and duplicate rules by id
    uniq: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for r in _RULES:
        rid = r.get("id") or r.get("rule_id")
        if r.get("deprecated"):
            continue
        if rid in seen:
            continue
        seen.add(rid)
        uniq.append(r)
    _RULES[:] = uniq


# load on import
load_rule_packs()

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def rules_count() -> int:
    return len(_RULES)


def loaded_packs() -> List[Dict[str, Any]]:
    return list(_PACKS)


def load_rules(base_dir: Path | None = None) -> List[Dict[str, Any]]:
    """Convenience wrapper returning loaded rules.

    If *base_dir* is provided, rules are loaded only from that directory for
    the duration of the call.
    """
    roots = [base_dir] if base_dir is not None else RULE_ROOTS
    load_rule_packs(roots)
    return list(_RULES)


def filter_rules(
    text: str,
    doc_type: str,
    clause_types: Iterable[str],
    jurisdiction: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Return (matched_rules, coverage).

    matched_rules: [{ "rule": <rule>, "matches": [evidence...] }]
    coverage: [{ "doc_type": ..., "jurisdiction": ..., "pack_id": ..., "rule_id": ...,
                 "severity": ..., "evidence": [...], "spans": [{"start":..,"end":..}],
                 "flags": <bitmask> }]
    """
    # Нормализация входа с сохранением \n; ошибки — в флаг
    flags_norm = 0
    try:
        norm = normalize_for_intake(text or "")
    except Exception:
        norm = text or ""
        flags_norm = TEXT_NORMALIZATION_ISSUE

    doc_type_lc = (doc_type or "").lower()
    juris_lc = (jurisdiction or "").lower()
    clause_set: Set[str] = {c.lower() for c in (clause_types or [])}

    filtered: List[Dict[str, Any]] = []
    coverage: List[Dict[str, Any]] = []

    candidate_ids = CANDIDATES_VAR.get()
    candidate_active = bool(candidate_ids)
    candidate_set: Set[str] = set(candidate_ids or [])

    for rule in _RULES:
        rule_id = str(rule.get("id") or rule.get("rule_id") or "")
        if candidate_active and rule_id not in candidate_set:
            continue
        rule_flags = flags_norm
        matches: List[str] = []
        spans: List[Dict[str, int]] = []

        # Gate: doc_type
        rule_doc_types = [d.lower() for d in rule.get("doc_types", [])]
        if doc_type_lc:
            if rule_doc_types and "any" not in rule_doc_types:
                if doc_type_lc not in rule_doc_types:
                    rule_flags |= DOC_TYPE_MISMATCH

        # Gate: jurisdiction
        rule_juris = [j.lower() for j in rule.get("jurisdiction", [])]
        if juris_lc:
            if rule_juris and "any" not in rule_juris:
                if juris_lc not in rule_juris:
                    rule_flags |= JURISDICTION_MISMATCH

        # Gate: requires_clause
        req_clauses = {c.lower() for c in rule.get("requires_clause", [])}
        if req_clauses and clause_set.isdisjoint(req_clauses):
            rule_flags |= NO_CLAUSE

        # Triggers
        ok = True
        trig = rule.get("triggers") or {}

        any_pats = trig.get("any")
        if any_pats:
            any_matches: List[str] = []
            for p in any_pats:
                for m in p.finditer(norm):
                    any_matches.append(m.group(0))
                    spans.append({"start": m.start(), "end": m.end()})
            if not any_matches:
                ok = False
                rule_flags |= REGEX_MISS
            else:
                matches.extend(any_matches)

        if ok:
            all_pats = trig.get("all")
            if all_pats:
                all_matches: List[str] = []
                for p in all_pats:
                    m = p.search(norm)
                    if not m:
                        ok = False
                        rule_flags |= REGEX_MISS
                        break
                    all_matches.append(m.group(0))
                    spans.append({"start": m.start(), "end": m.end()})
                if ok:
                    matches.extend(all_matches)

        if ok:
            regex_pats = trig.get("regex")
            if regex_pats:
                regex_matches: List[str] = []
                for p in regex_pats:
                    for m in p.finditer(norm):
                        regex_matches.append(m.group(0))
                        spans.append({"start": m.start(), "end": m.end()})
                if not regex_matches:
                    ok = False
                    rule_flags |= REGEX_MISS
                else:
                    matches.extend(regex_matches)

        # Матч засчитываем только если нет gate-флагов и триггеры прошли
        if ok and not rule_flags:
            rule_flags |= FIRED
            filtered.append({"rule": rule, "matches": matches})

        coverage.append(
            {
                "doc_type": doc_type_lc,
                "jurisdiction": juris_lc,
                "pack_id": rule.get("pack"),
                "rule_id": rule_id,
                "severity": rule.get("severity"),
                "evidence": matches,
                "spans": spans,
                "flags": rule_flags,
            }
        )

    if not filtered:
        baseline_rules = _get_baseline_rules()
        if baseline_rules:
            for rule in baseline_rules:
                filtered.append({"rule": rule, "matches": []})
                coverage.append(
                    {
                        "doc_type": doc_type_lc,
                        "jurisdiction": juris_lc,
                        "pack_id": rule.get("pack"),
                        "rule_id": rule.get("id"),
                        "severity": rule.get("severity"),
                        "evidence": [],
                        "spans": [],
                        "flags": 0,
                    }
                )

    return filtered, coverage


@lru_cache(maxsize=1)
def _get_baseline_rules() -> List[Dict[str, Any]]:
    """Load baseline pattern rules used as a fallback when filtering yields none."""

    if not BASELINE_FILE.exists():
        return []

    try:
        raw_docs = list(yaml.safe_load_all(BASELINE_FILE.read_text(encoding="utf-8")))
    except Exception as exc:  # pragma: no cover
        log.error("Failed to load baseline patterns: %s", exc)
        return []

    specs: List[Dict[str, Any]] = []
    try:
        pack_id = str(BASELINE_FILE.relative_to(ROOT_DIR))
    except ValueError:  # pragma: no cover
        pack_id = str(BASELINE_FILE)

    def _flatten(doc: Any) -> Iterable[Dict[str, Any]]:
        if not doc:
            return []
        if isinstance(doc, dict) and doc.get("rules"):
            return list(doc.get("rules") or [])
        if isinstance(doc, dict) and doc.get("rule"):
            return [doc.get("rule")]
        if isinstance(doc, dict):
            return [doc]
        if isinstance(doc, list):
            return list(doc)
        return []

    for doc in raw_docs:
        for idx, raw in enumerate(_flatten(doc)):
            if not isinstance(raw, dict):
                continue
            rid = str(raw.get("id") or raw.get("rule_id") or f"baseline-{idx}")
            compiled = _compile(raw.get("patterns", []) or [])
            specs.append(
                {
                    "id": rid,
                    "rule_id": rid,
                    "Title": raw.get("Title"),
                    "title": raw.get("title"),
                    "clause_type": raw.get("clause_type"),
                    "severity": str(raw.get("severity") or "low").lower(),
                    "patterns": compiled,
                    "advice": raw.get("advice") or "",
                    "law_refs": list(raw.get("law_refs") or []),
                    "suggestion": raw.get("suggestion"),
                    "conflict_with": list(raw.get("conflict_with") or []),
                    "ops": raw.get("ops") or [],
                    "pack": pack_id,
                    "triggers": {},
                    "requires_clause_hit": False,
                    "doc_types": [],
                    "jurisdiction": [],
                    "requires_clause": [],
                    "deprecated": False,
                }
            )

    return specs


def match_text(text: str) -> List[Dict[str, Any]]:
    from . import engine

    return engine.analyze(text or "", _RULES)
