"""YAML rule loader for policy and core rule packs."""
from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

log = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
POLICY_DIR = Path(__file__).resolve().parent / "policy_packs"
CORE_RULES_DIR = ROOT_DIR / "core" / "rules"

_ENV_DIRS = os.getenv("RULE_PACKS_DIRS")
if _ENV_DIRS:
    RULE_PACKS_DIRS = [Path(p.strip()) for p in _ENV_DIRS.split(os.pathsep) if p.strip()]
else:
    RULE_PACKS_DIRS = [POLICY_DIR, CORE_RULES_DIR]


_RULES: List[Dict[str, Any]] = []
_PACKS: List[Dict[str, Any]] = []


def _compile(patterns: Iterable[str]) -> List[re.Pattern[str]]:
    return [re.compile(p, re.I | re.MULTILINE) for p in patterns if p]


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
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception as exc:  # pragma: no cover - load error
                log.error("Failed to load %s: %s", path, exc)
                continue

            rules_iter: List[Dict[str, Any]]
            if isinstance(data, dict) and data.get("rule"):
                rules_iter = [data["rule"]]
            elif isinstance(data, dict) and data.get("rules"):
                rules_iter = list(data.get("rules") or [])
            elif isinstance(data, list):
                rules_iter = list(data)
            else:
                rules_iter = []

            rule_count = 0
            for raw in rules_iter:
                pats: List[str] = []
                if raw.get("patterns"):
                    pats = list(raw.get("patterns", []))
                else:
                    for cond in raw.get("triggers", {}).get("any", []):
                        if isinstance(cond, dict):
                            pat = cond.get("regex")
                        else:
                            pat = cond
                        if pat:
                            pats.append(pat)
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
                    "patterns": _compile(pats),
                    "advice": raw.get("advice")
                    or raw.get("intent")
                    or (raw.get("finding", {}) or {}).get("suggestion", {}).get("text")
                    or (raw.get("finding", {}) or {}).get("message"),
                    "law_refs": list(
                        raw.get("law_reference")
                        or raw.get("law_refs")
                        or []
                    ),
                    "conflict_with": list(raw.get("conflict_with") or []),
                    "ops": raw.get("ops") or [],
                }
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

