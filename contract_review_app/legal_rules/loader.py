"""YAML rule loader for policy and core rule packs."""

from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..corpus.normalizer import normalize_text


def _normalize_multiline(text: str) -> str:
    """Normalize ``text`` while preserving line breaks."""
    return "\n".join(normalize_text(line) for line in (text or "").splitlines())


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


# Bit flags representing gating results for rule coverage
SCHEMA_MISMATCH = 1 << 0
DOC_TYPE_MISMATCH = 1 << 1
JURISDICTION_MISMATCH = 1 << 2
NO_CLAUSE = 1 << 3
REGEX_MISS = 1 << 4
WHEN_FALSE = 1 << 5
TEXT_NORMALIZATION_ISSUE = 1 << 6
FIRED = 1 << 7


def _compile(patterns: Iterable[str]) -> List[re.Pattern[str]]:
    return [re.compile(p, re.I | re.MULTILINE) for p in patterns if p]


class RuleSchema(BaseModel):
    """Pydantic model validating the unified rule specification."""

    rule_id: str = Field(alias="id")
    doc_types: List[str] = Field(default_factory=list)
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

    for base in RULE_PACKS_DIRS:
        if not base.exists():
            continue
        if base.samefile(POLICY_DIR):
            paths = sorted(base.glob("*.yaml"))
        else:
            paths = sorted(base.rglob("*.yaml"))
        for path in paths:
            try:
                docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            except Exception as exc:  # pragma: no cover - load error
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
                    pats: List[str] = []
                    trig_any = raw.get("triggers", {}).get("any", []) or []
                    trig_all = raw.get("triggers", {}).get("all", []) or []
                    trig_regex = raw.get("triggers", {}).get("regex", []) or []

                    if raw.get("patterns"):
                        pats = list(raw.get("patterns", []))
                    else:
                        for cond in trig_any:
                            pat = cond.get("regex") if isinstance(cond, dict) else cond
                            if pat:
                                pats.append(pat)
                        for cond in trig_all:
                            pat = cond.get("regex") if isinstance(cond, dict) else cond
                            if pat:
                                pats.append(pat)
                        for cond in trig_regex:
                            pat = cond.get("regex") if isinstance(cond, dict) else cond
                            if pat:
                                pats.append(pat)

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
                            [c.get("regex") if isinstance(c, dict) else c for c in trig_any]
                        )
                    if trig_all:
                        trig_map["all"] = _compile(
                            [c.get("regex") if isinstance(c, dict) else c for c in trig_all]
                        )
                    if trig_regex or raw.get("patterns"):
                        trig_map["regex"] = _compile(
                            [
                                c.get("regex") if isinstance(c, dict) else c
                                for c in (trig_regex or raw.get("patterns", []))
                            ]
                        )

                    doc_types = list(
                        raw.get("doc_types")
                        or (raw.get("scope", {}) or {}).get("doc_types")
                        or []
                    )
                    requires_clause = list(
                        raw.get("requires_clause")
                        or (raw.get("scope", {}) or {}).get("clauses")
                        or []
                    )
                    deprecated = bool(raw.get("deprecated"))

                    spec = {
                        "id": raw.get("id"),
                        "clause_type": raw.get("clause_type")
                        or (raw.get("scope", {}) or {}).get("clauses", [None])[0],
                        "severity": str(
                            raw.get("severity")
                            or raw.get("risk")
                            or raw.get("severity_level")
                            or "medium",
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
                        "pack": str(path.relative_to(ROOT_DIR)),
                        "triggers": trig_map,
                        "requires_clause_hit": bool(raw.get("requires_clause_hit")),
                        "doc_types": doc_types,
                        "requires_clause": requires_clause,
                        "deprecated": deprecated,
                    }

                    try:
                        RuleSchema.model_validate(
                            {
                                "id": spec["id"],
                                "doc_types": doc_types,
                                "severity": spec["severity"],
                                "triggers": {
                                    k: [p.pattern for p in v] for k, v in trig_map.items()
                                },
                                "requires_clause": requires_clause,
                                "advice": spec["advice"],
                                "law_refs": spec["law_refs"],
                                "deprecated": deprecated,
                            }
                        )
                    except ValidationError:
                        # Backward-compat: не прерываем загрузку;
                        # аудит и CI-проверки используют ту же схему отдельно.
                        pass

                    _RULES.append(spec)
                    rule_count += 1

            rel = path.relative_to(ROOT_DIR)
            _PACKS.append({"path": str(rel), "rule_count": rule_count})


# load on import
load_rule_packs()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def rules_count() -> int:
    return len(_RULES)


def loaded_packs() -> List[Dict[str, Any]]:
    return list(_PACKS)


def filter_rules(
    text: str, doc_type: str, clause_types: Iterable[str]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return matched rules and coverage info for all rules.

    Returns:
        (filtered, coverage):
          filtered: [{ "rule": <rule>, "matches": [..] }]
          coverage: [{
              "doc_type": str,
              "pack_id": str,
              "rule_id": str,
              "severity": str,
              "evidence": [..],
              "spans": [{"start": int, "end": int}, ...],
              "flags": int (bitwise)
          }]
    """
    flags_norm = 0
    try:
        # сохраняем переносы строк для якорей ^...$ при MULTILINE
        norm = _normalize_multiline(text or "")
    except Exception:  # крайне редкий случай проблем нормализации
        flags_norm = TEXT_NORMALIZATION_ISSUE
        norm = text or ""

    doc_type_lc = (doc_type or "").lower()
    clause_set: Set[str] = {c.lower() for c in clause_types or []}

    filtered: List[Dict[str, Any]] = []
    coverage: List[Dict[str, Any]] = []
    for rule in _RULES:
        rule_flags = flags_norm
        matches: List[str] = []
        spans: List[Dict[str, int]] = []

        rule_doc_types = [d.lower() for d in rule.get("doc_types", [])]
        if rule_doc_types and "any" not in rule_doc_types:
            if not doc_type_lc or doc_type_lc not in rule_doc_types:
                rule_flags |= DOC_TYPE_MISMATCH

        req_clauses = {c.lower() for c in rule.get("requires_clause", [])}
        if req_clauses and clause_set.isdisjoint(req_clauses):
            rule_flags |= NO_CLAUSE

        if rule_flags & (DOC_TYPE_MISMATCH | NO_CLAUSE):
            coverage.append(
                {
                    "doc_type": doc_type_lc,
                    "pack_id": rule.get("pack"),
                    "rule_id": rule.get("id"),
                    "severity": rule.get("severity"),
                    "evidence": matches,
                    "spans": spans,
                    "flags": rule_flags,
                }
            )
            continue

        trig = rule.get("triggers") or {}
        ok = True

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
                for pat in all_pats:
                    m = pat.search(norm)
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

        if ok and not rule_flags:
            rule_flags |= FIRED
            filtered.append({"rule": rule, "matches": matches})

        coverage.append(
            {
                "doc_type": doc_type_lc,
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
