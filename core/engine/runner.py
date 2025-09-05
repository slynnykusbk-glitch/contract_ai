"""Minimal YAML rule runner for tests.

This simple engine supports loading a YAML rule specification and
executing basic regex based checks against input text.
"""
from __future__ import annotations

import re
import yaml
from dataclasses import dataclass
from typing import Any, Dict, List

from core.schemas import AnalysisInput


@dataclass
class Finding:
    """Simplified finding used in tests."""
    message: str


@dataclass
class RuleResult:
    """Result returned by :func:`run_rule`.

    Only the fields accessed in tests are implemented.
    """
    findings: List[Finding]
    risk_level: str


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def load_rule(path: str) -> Dict[str, Any]:
    """Load a YAML rule file and return its ``rule`` section."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # The rule spec is under the top-level key ``rule``.
    return data.get("rule", data)


def _eval_condition(cond: Dict[str, str], text: str) -> bool:
    if "regex" in cond:
        return re.search(cond["regex"], text) is not None
    if "not_regex" in cond:
        return re.search(cond["not_regex"], text) is None
    return False


def run_rule(spec: Dict[str, Any], inp: AnalysisInput) -> RuleResult | None:
    """Execute checks defined in ``spec`` against ``inp.text``.

    If no findings are produced, ``None`` is returned to mirror the
    behaviour of the full engine used in production.
    """
    text = inp.text or ""
    findings: List[Finding] = []
    max_risk = "low"

    for check in spec.get("checks", []):
        when = check.get("when", {})
        triggered = False
        if "any" in when:
            triggered = any(_eval_condition(c, text) for c in when["any"])
        elif "all" in when:
            triggered = all(_eval_condition(c, text) for c in when["all"])
        else:
            triggered = _eval_condition(when, text) if when else False

        if triggered:
            f_spec = check.get("finding", {})
            msg = f_spec.get("message", "")
            risk = f_spec.get("risk", "low")
            findings.append(Finding(message=msg))
            if _RISK_ORDER.get(risk, 0) > _RISK_ORDER.get(max_risk, 0):
                max_risk = risk

    if not findings:
        return None
    return RuleResult(findings=findings, risk_level=max_risk)
