"""Minimal YAML rule runner for tests.

This simple engine supports loading a YAML rule specification and
executing basic regex based checks against input text.
"""

from __future__ import annotations

import re
import yaml
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.schemas import AnalysisInput


@dataclass
class Finding:
    """Simplified finding used in tests."""

    message: str
    suggestion: Optional["Suggestion"] = None
    legal_basis: List[str] | None = None


@dataclass
class Suggestion:
    text: str = ""


@dataclass
class RuleResult:
    """Result returned by :func:`run_rule`.

    Only the fields accessed in tests are implemented.
    """

    findings: List[Finding]
    risk_level: str


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def load_rule(path: str, rule_id: str | None = None) -> Dict[str, Any]:
    """Load a YAML rule file and return a specific ``rule`` section.

    The helper used in tests originally loaded a single-rule YAML file.
    For authoring convenience, rule packs may now contain multiple YAML
    documents separated by ``---``.  When ``rule_id`` is provided this
    function searches all documents and returns the matching rule.  If no
    ``rule_id`` is given the first document's rule is returned.
    """

    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))

    def _extract(doc: Dict[str, Any]):
        if "rules" in doc and isinstance(doc["rules"], list):
            return list(doc["rules"])
        return [doc.get("rule", doc)]

    all_rules: List[Dict[str, Any]] = []
    for doc in docs:
        all_rules.extend(_extract(doc))

    if rule_id:
        for rule in all_rules:
            if rule.get("id") == rule_id:
                return rule
        raise ValueError(f"rule_id {rule_id} not found in {path}")

    return all_rules[0] if all_rules else {}


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

    # Rule-level trigger evaluation
    trig = spec.get("triggers") or {}
    if trig:
        if "any" in trig and not any(_eval_condition(c, text) for c in trig["any"]):
            return None
        if "all" in trig and not all(_eval_condition(c, text) for c in trig["all"]):
            return None

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
            s_spec = f_spec.get("suggestion")
            suggestion = None
            if isinstance(s_spec, dict):
                suggestion = Suggestion(text=s_spec.get("text", ""))
            legal_basis = f_spec.get("legal_basis") or []
            findings.append(
                Finding(message=msg, suggestion=suggestion, legal_basis=legal_basis)
            )
            if _RISK_ORDER.get(risk, 0) > _RISK_ORDER.get(max_risk, 0):
                max_risk = risk

    if not findings:
        return None
    return RuleResult(findings=findings, risk_level=max_risk)
