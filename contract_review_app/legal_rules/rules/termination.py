from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output

rule_name = "termination"

def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    if not re.search(r"\bterminat(e|ion)\b", text, flags=re.I):
        findings.append(mk_finding("TER-ABSENT", "No termination clause detected", "medium"))
        return make_output(rule_name, inp, findings, "Termination", "Termination")

    # For cause & cure period
    if re.search(r"\bfor cause\b|\bmaterial breach\b", text, flags=re.I):
        if not re.search(r"\b(cure|remed(y|ies))\b", text, flags=re.I):
            findings.append(mk_finding("TER-CURE", "For-cause termination without cure period", "high"))
        if not re.search(r"\b\d{1,3}\s*(calendar\s*)?days?\b", text, flags=re.I):
            findings.append(mk_finding("TER-NOTICE", "No explicit notice period for termination", "medium"))

    # Convenience termination
    if re.search(r"\bfor convenience\b|\bat any time\b", text, flags=re.I) and not re.search(r"\bnotice\b", text, flags=re.I):
        findings.append(mk_finding("TER-CONV-NOTICE", "Termination for convenience without notice", "high"))

    # Effects of termination
    if not re.search(r"\beffects? of termination\b|\bconsequences of termination\b", text, flags=re.I):
        findings.append(mk_finding("TER-EFFECTS", "No 'Effects of termination' (return materials, survival, fees)", "medium"))

    return make_output(rule_name, inp, findings, "Termination", "Termination")
