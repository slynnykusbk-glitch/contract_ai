# contract_review_app/legal_rules/rules/base.py
from __future__ import annotations
import re
from typing import List, Dict, Any
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput

_SEV_MAP = {"low": "info", "medium": "minor", "high": "major", "critical": "critical"}

def mk_finding(code: str, message: str, severity: str = "medium", start: int = 0, length: int = 0) -> Dict[str, Any]:
    sev = _SEV_MAP.get(str(severity).lower(), str(severity))
    return {
        "code": code,
        "message": message,
        "severity": sev,
        "span": {"start": max(0, start), "length": max(0, length)},
    }

def risk_from_findings(findings: List[Dict[str, Any]]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    r_inv = {0: "low", 1: "medium", 2: "high", 3: "critical"}
    lvl = 0
    for f in findings:
        lvl = max(lvl, order.get(str(f.get("severity", "medium")).lower(), 1))
    return r_inv[lvl]

def score_from_findings(findings: List[Dict[str, Any]], base: int = 95) -> int:
    penalty = 0
    for f in findings:
        sev = str(f.get("severity", "medium")).lower()
        penalty += {"low": 1, "medium": 3, "high": 10, "critical": 20}.get(sev, 3)
    return max(0, min(100, base - penalty))

def status_from_risk(risk: str) -> str:
    risk = (risk or "").lower()
    if risk in ("critical",):
        return "FAIL"
    if risk in ("high",):
        return "WARN"
    return "OK"

def find_span(text: str, pattern: str) -> tuple[int, int]:
    m = re.search(pattern, text, flags=re.I)
    if not m:
        return 0, 0
    return m.start(), m.end() - m.start()

def make_output(rule_name: str, inp: AnalysisInput, findings: List[Dict[str, Any]], category: str, clause_name: str) -> AnalysisOutput:
    risk = risk_from_findings(findings)
    score = score_from_findings(findings)
    return AnalysisOutput(
        clause_type=rule_name,
        text=inp.text or "",
        status=status_from_risk(risk),
        score=score,
        risk=risk,
        findings=findings,
        recommendations=[],
        citations=[],
        diagnostics=[],
        trace=[],
        category=category,
        clause_name=clause_name,
    )
