from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output

rule_name = "jurisdiction"

def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    has_excl = re.search(r"\bexclusive jurisdiction\b", text, flags=re.I)
    has_non  = re.search(r"\bnon[- ]exclusive jurisdiction\b", text, flags=re.I)
    has_courts = re.search(r"\bcourts? of\b", text, flags=re.I)

    if not (has_excl or has_non or has_courts):
        findings.append(mk_finding("JUR-ABSENT", "No jurisdiction/forum selection stated", "high"))

    if has_excl and has_non:
        findings.append(mk_finding("JUR-CONFLICT", "Both 'exclusive' and 'non-exclusive' jurisdiction detected", "high"))

    return make_output(rule_name, inp, findings, "Jurisdiction", "Jurisdiction")
