"""YAML rule loader for policy and core rule packs."""

from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

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
                            if isinstance(cond, dict):
                                pat = cond.get("regex")
                            else:
                                pat = cond
                            if pat:
                                pats.append(pat)
                        for cond in trig_all:
                            if isinstance(cond, dict):
                                pat = cond.get("regex")
                            else:
                                pat = cond
                            if pat:
                                pats.append(pat)
                        for cond in trig_regex:
                            if isinstance(cond, dict):
                                pat = cond.get("regex")
                            else:
                                pat = cond
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
                            [
                                c.get("regex") if isinstance(c, dict) else c
                                for c in trig_any
                            ]
                        )
                    if trig_all:
                        trig_map["all"] = _compile(
                            [
                                c.get("regex") if isinstance(c, dict) else c
                                for c in trig_all
                            ]
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
                                    k: [p.pattern for p in v]
                                    for k, v in trig_map.items()
                                },
                                "requires_clause": requires_clause,
                                "advice": spec["advice"],
                                "law_refs": spec["law_refs"],
                                "deprecated": deprecated,
                            }
                        )
                    except ValidationError:
                        # For backward compatibility we do not abort loading on
                        # validation errors.  The audit tool and CI checks use
                        # the same model to report issues separately.
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


def match_text(text: str) -> List[Dict[str, Any]]:
    from . import engine

    return engine.analyze(text or "", _RULES)
