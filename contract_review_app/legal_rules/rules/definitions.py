from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output

rule_name = "definitions"

def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    # Heading presence
    if not re.search(r"\bdefinitions?\b", text, flags=re.I):
        findings.append(mk_finding("DEF-HEAD", "Missing explicit 'Definitions' heading", "medium"))

    # Uppercase terms (at least some)
    terms = re.findall(r"\b[A-Z][A-Z_ ]{2,}\b", text)
    if len(terms) < 3:
        findings.append(mk_finding("DEF-TERMS", "Few or no defined terms detected (UPPERCASE)", "medium"))

    # “Confidential Information” consistency example
    if re.search(r"confidential information", text, flags=re.I) and not re.search(r"means|shall mean|is defined as", text, flags=re.I):
        start, end = re.search(r"confidential information", text, flags=re.I).span()
        findings.append(
            mk_finding(
                "DEF-CI-DEF",
                "Confidential Information mentioned but not clearly defined",
                "high",
                start,
                end,
            )
        )

    return make_output(rule_name, inp, findings, "Definitions", "Definitions")
