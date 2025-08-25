from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output, find_span

rule_name = "force_majeure"

def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    if not re.search(r"\bforce majeure\b", text, flags=re.I):
        findings.append(mk_finding("FM-ABSENT", "No 'Force Majeure' provision detected", "medium"))
    else:
        # Notice requirement
        if not re.search(r"\bnotice\b", text, flags=re.I):
            start, length = find_span(text, r"force majeure")
            findings.append(
                mk_finding("FM-NOTICE", "No notice obligation during force majeure", "medium", start, length)
            )
        # Mitigation duty
        if not re.search(r"\bmitigat(e|ion)\b", text, flags=re.I):
            findings.append(mk_finding("FM-MITIG", "No duty to mitigate effects of force majeure", "low"))
        # Payment obligations carve-out (optional policy)
        if re.search(r"\bpayment\b", text, flags=re.I) and re.search(r"\bexcuse\b|\bsuspend\b", text, flags=re.I):
            findings.append(mk_finding("FM-PAY", "Payment obligations appear excused by FM (check policy)", "medium"))

    return make_output(rule_name, inp, findings, "Force Majeure", "Force Majeure")
