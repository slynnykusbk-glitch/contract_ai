"""Lightweight YAML rule loader and matcher."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

PLACEHOLDER_RE = re.compile(r"\[(?:DELETE AS APPROPRIATE|●)\]", re.I)

# ---------------------------------------------------------------------------
# Load and compile rules on import
# ---------------------------------------------------------------------------
_RULES: List[Dict[str, Any]] = []


def _compile(patterns: Iterable[str]) -> List[re.Pattern[str]]:
    return [re.compile(p, re.I | re.MULTILINE) for p in patterns if p]


def load_rule_packs(packs: Optional[List[str]] = None) -> None:
    """Load YAML rule packs by name. If ``packs`` is None all packs are loaded."""

    _RULES.clear()
    base = Path(__file__).resolve().parent / "policy_packs"
    if not base.exists():
        return
    for path in base.glob("*.yaml"):
        if packs and path.stem not in packs:
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for raw in data.get("rules") or []:
            if "patterns" in raw:  # legacy schema
                _RULES.append(
                    {
                        "id": raw.get("id"),
                        "clause_type": raw.get("clause_type"),
                        "severity": raw.get("severity"),
                        "patterns": _compile(raw.get("patterns", [])),
                        "advice": raw.get("advice"),
                    }
                )
            else:  # msa_oilgas schema
                triggers = _compile(raw.get("triggers", {}).get("any", []))
                include = _compile(raw.get("checks", {}).get("must_include", []))
                exclude = _compile(raw.get("checks", {}).get("must_exclude", []))
                _RULES.append(
                    {
                        "id": raw.get("id"),
                        "clause_type": raw.get("clause_type"),
                        "severity": raw.get("severity"),
                        "triggers": triggers,
                        "include": include,
                        "exclude": exclude,
                        "placeholders_forbidden": bool(raw.get("placeholders_forbidden")),
                        "advice": raw.get("intent"),
                    }
                )


# load all packs on import
load_rule_packs()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def discover_rules() -> List[Dict[str, Any]]:
    """Return loaded rules without compiled regex objects."""
    out: List[Dict[str, Any]] = []
    for r in _RULES:
        if r.get("patterns"):
            pats = [p.pattern for p in r.get("patterns", [])]
        else:
            pats = [p.pattern for p in r.get("triggers", [])]
        out.append(
            {
                "id": r.get("id"),
                "clause_type": r.get("clause_type"),
                "severity": r.get("severity"),
                "patterns": pats,
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
        if r.get("placeholders_forbidden"):
            for m in PLACEHOLDER_RE.finditer(text):
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
        if r.get("patterns"):
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
        else:
            trig_match = None
            for t in r.get("triggers", []):
                m = t.search(text)
                if m:
                    trig_match = m
                    break
            if not trig_match:
                continue
            if any(inc.search(text) is None for inc in r.get("include", [])):
                continue
            if any(exc.search(text) for exc in r.get("exclude", [])):
                continue
            findings.append(
                {
                    "rule_id": r.get("id"),
                    "clause_type": r.get("clause_type"),
                    "severity": r.get("severity"),
                    "start": trig_match.start(),
                    "end": trig_match.end(),
                    "snippet": text[trig_match.start() : trig_match.end()],
                    "advice": r.get("advice"),
                }
            )
    return findings

