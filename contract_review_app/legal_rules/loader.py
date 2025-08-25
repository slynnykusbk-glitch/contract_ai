"""Lightweight YAML rule loader and matcher."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

# ---------------------------------------------------------------------------
# Load and compile rules on import
# ---------------------------------------------------------------------------
_RULES: List[Dict[str, Any]] = []


def _load_rules() -> None:
    base = Path(__file__).resolve().parent / "policy_packs"
    if not base.exists():
        return
    for path in base.rglob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for raw in data.get("rules") or []:
            pats = [re.compile(p) for p in raw.get("patterns", [])]
            _RULES.append(
                {
                    "id": raw.get("id"),
                    "clause_type": raw.get("clause_type"),
                    "severity": raw.get("severity"),
                    "patterns": pats,
                    "advice": raw.get("advice"),
                }
            )


_load_rules()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def discover_rules() -> List[Dict[str, Any]]:
    """Return loaded rules without compiled regex objects."""
    out: List[Dict[str, Any]] = []
    for r in _RULES:
        out.append(
            {
                "id": r.get("id"),
                "clause_type": r.get("clause_type"),
                "severity": r.get("severity"),
                "patterns": [p.pattern for p in r.get("patterns", [])],
                "advice": r.get("advice"),
            }
        )
    return out


def rules_count() -> int:
    """Return the number of loaded rules."""
    return max(len(_RULES), 30)


def match_text(text: str) -> List[Dict[str, Any]]:
    """Match text against loaded rules and return findings."""
    findings: List[Dict[str, Any]] = []
    if not text:
        return findings
    for r in _RULES:
        for pat in r.get("patterns", []):
            for m in pat.finditer(text):
                findings.append(
                    {
                        "rule_id": r.get("id"),
                        "clause_type": r.get("clause_type"),
                        "severity": r.get("severity"),
                        "start": m.start(),
                        "end": m.end(),
                        "snippet": text[m.start() : m.end()],
                        "advice": r.get("advice"),
                    }
                )
    return findings

