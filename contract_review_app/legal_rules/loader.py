# contract_review_app/legal_rules/loader.py
"""YAML rule loader for policy and core rule packs."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

# Новая нормализация при intake: кавычки/дефисы -> ASCII, сжатие пробелов, сохранение \n
from ..intake.normalization import normalize_for_intake

log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
POLICY_DIR = Path(__file__).resolve().parent / "policy_packs"
CORE_RULES_DIR = ROOT_DIR / "core" / "rules"

_ENV_DIRS = os.getenv("RULE_PACKS_DIRS")
if _ENV_DIRS:
    RULE_PACKS_DIRS = [
        Path(p.strip()) for p in _ENV_DIRS.split(os.pathsep) if p.strip()
    ]
else:
    RULE_PACKS_DIRS = [POLICY_DIR, CORE_RULES_DIR]

_RULES: List[Dict[str, Any]] = []
_PACKS: List[Dict[str, Any]] = []

ALLOWED_RULE_EXTS = {".yml", ".yaml"}

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


def load_rule_packs() -> None:
    """Load YAML rule packs from configured directories."""
    _RULES.clear()
    _PACKS.clear()

    warned_py = False
    for base in RULE_PACKS_DIRS:
        if not base.exists():
            continue

        paths = (
            sorted(p for p in base.glob("*") if p.is_file())
            if base.samefile(POLICY_DIR)
            else sorted(p for p in base.rglob("*") if p.is_file())
        )
        for path in paths:
            if "_legacy_disabled" in path.parts:
                continue
            suffix = path.suffix.lower()
            if suffix not in ALLOWED_RULE_EXTS:
                if suffix == ".py" and not warned_py:
                    log.warning("Skipped legacy Python rules (*.py).")
                    warned_py = True
                continue
            try:
                docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            except Exception as exc:  # pragma: no cover
                log.error("Failed to load %s: %s", path, exc)
                continue

            rule_count = 0
            for data in docs:
                if not data:
                    continue

                if isinstance(data, dict) and data.get("rule"):
                    rules_iter: List[Dict[str, Any]] = [data["rule"]]
                elif isinstance(data, dict) and data.get("rules"):
                    rules_iter = list(data.get("rules") or [])
                elif isinstance(data, list):
                    rules_iter = list(data)
                else:
                    rules_iter = []

                for raw in rules_iter:
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

                    spec = {
                        "id": raw.get("id"),
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

                    _RULES.append(spec)
                    rule_count += 1

            try:
                rel = path.relative_to(ROOT_DIR)
            except ValueError:  # pragma: no cover
                rel = path
            _PACKS.append({"path": str(rel), "rule_count": rule_count})
    # Remove deprecated and duplicate rules by id
    uniq: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for r in _RULES:
        rid = r.get("id")
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
    if base_dir is not None:
        old_dirs = list(RULE_PACKS_DIRS)
        try:
            RULE_PACKS_DIRS[:] = [Path(base_dir)]
            load_rule_packs()
            return list(_RULES)
        finally:
            RULE_PACKS_DIRS[:] = old_dirs
            load_rule_packs()
    else:
        load_rule_packs()
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

    for rule in _RULES:
        rule_flags = flags_norm
        matches: List[str] = []
        spans: List[Dict[str, int]] = []

        # Gate: doc_type
        rule_doc_types = [d.lower() for d in rule.get("doc_types", [])]
        if rule_doc_types and "any" not in rule_doc_types:
            if not doc_type_lc or doc_type_lc not in rule_doc_types:
                rule_flags |= DOC_TYPE_MISMATCH

        # Gate: jurisdiction
        rule_juris = [j.lower() for j in rule.get("jurisdiction", [])]
        if rule_juris and "any" not in rule_juris:
            if not juris_lc or juris_lc not in rule_juris:
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
                "rule_id": rule.get("id"),
                "severity": rule.get("severity"),
                "evidence": matches,
                "spans": spans,
                "flags": rule_flags,
            }
        )

    return filtered, coverage


def match_text(text: str) -> List[Dict[str, Any]]:
    from . import engine

    return engine.analyze(text or "", _RULES)
