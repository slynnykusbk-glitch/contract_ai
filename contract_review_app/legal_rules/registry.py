from __future__ import annotations

from typing import Any, Dict, List

from .loader import Rule, discover_rules as _discover_rules


def discover_rules() -> List[Rule]:
    """Expose loaded rules for diagnostics."""

    return _discover_rules(include_yaml=True)


def run_all(text: str) -> Dict[str, Any]:
    """Run all discovered rules against the provided text."""

    findings: List[Dict[str, Any]] = []
    for rule in discover_rules():
        for pat in rule.patterns:
            m = pat.search(text or "")
            if m:
                findings.append(
                    {
                        "rule_id": rule.id,
                        "clause_type": rule.clause_type,
                        "severity": rule.severity,
                        "matched_text": m.group(0),
                        "advice": rule.advice,
                    }
                )
                break

    return {
        "analysis": {
            "status": "OK",
            "clause_type": "general",
            "risk_level": "medium",
            "score": 0,
            "findings": findings,
        },
        "results": {},
        "clauses": [],
        "document": {"text": text or ""},
    }

