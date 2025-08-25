"""Lightweight YAML rule loader and matcher."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

_PLACEHOLDER_RE = re.compile(
    r"\[\s*●\s*\]|\[DELETE AS APPROPRIATE\]|\bTBC\b", re.IGNORECASE
)

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
            pats: List[re.Pattern] = []
            triggers = (raw.get("triggers") or {}).get("any", [])
            for p in triggers:
                try:
                    pats.append(re.compile(p, re.IGNORECASE | re.MULTILINE | re.DOTALL))
                except re.error:
                    continue
            for p in raw.get("patterns", []):
                try:
                    pats.append(re.compile(p))
                except re.error:
                    continue
            _RULES.append(
                {
                    "id": raw.get("id"),
                    "clause_type": raw.get("clause_type"),
                    "severity": raw.get("severity"),
                    "patterns": pats,
                    "advice": raw.get("intent") or raw.get("advice"),
                    "placeholders_forbidden": bool(raw.get("placeholders_forbidden")),
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
    return len(_RULES)


def match_text(text: str) -> List[Dict[str, Any]]:
    """Match text against loaded rules and return findings."""
    findings: List[Dict[str, Any]] = []
    if not text:
        return findings
    for r in _RULES:
        for pat in r.get("patterns", []):
            for m in pat.finditer(text):
                snippet = text[m.start() : m.end()]
                finding: Dict[str, Any] = {
                    "rule_id": r.get("id"),
                    "clause_type": r.get("clause_type"),
                    "severity": r.get("severity"),
                    "start": m.start(),
                    "end": m.end(),
                    "snippet": snippet,
                    "advice": r.get("advice"),
                }
                if r.get("placeholders_forbidden") and _PLACEHOLDER_RE.search(snippet):
                    finding["placeholder"] = True
                findings.append(finding)
    return findings

