from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output

rule_name = "indemnity"

def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    if not re.search(r"\bindemnif(y|ication)\b|\bhold harmless\b", text, flags=re.I):
        findings.append(mk_finding("IND-ABSENT", "No indemnity obligation detected", "medium"))
        return make_output(rule_name, inp, findings, "Indemnity", "Indemnity")

    # Mutuality
    if not re.search(r"\b(each party|mutual(ly)?)\b", text, flags=re.I):
        findings.append(mk_finding("IND-MUTUAL", "Indemnity appears one-sided (consider mutual)", "medium"))

    # Exclusions
    if not re.search(r"\b(except|excluding|save that)\b.*\b(gross negligence|wilful misconduct)\b", text, flags=re.I):
        findings.append(mk_finding("IND-EXC", "No exclusions for gross negligence / wilful misconduct", "high"))

    # Caps / limitations (hint)
    if not re.search(r"\b(cap|limit(ed)? to|liability cap)\b", text, flags=re.I):
        findings.append(mk_finding("IND-CAP", "No cap/limit reference for indemnity exposure", "high"))

    return make_output(rule_name, inp, findings, "Indemnity", "Indemnity")
