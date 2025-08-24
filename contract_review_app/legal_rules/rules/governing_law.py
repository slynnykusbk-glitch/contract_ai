from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output

rule_name = "governing_law"

LAW_RE = r"(laws? of (england(?: and wales)?|scotland|northern ireland|united kingdom|uk))"

def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    if not re.search(r"\bgoverning law\b|\bthis agreement is governed by\b", text, flags=re.I):
        findings.append(mk_finding("GL-ABSENT", "No explicit governing law statement", "critical"))
    else:
        if not re.search(LAW_RE, text, flags=re.I):
            findings.append(mk_finding("GL-JUR", "Governing law lacks specific jurisdiction (e.g., 'laws of England and Wales')", "high"))

    if not re.search(r"\bcourts? of\b|\bexclusive jurisdiction\b|\bnon[- ]exclusive jurisdiction\b", text, flags=re.I):
        findings.append(mk_finding("GL-JURISD", "No forum/jurisdiction clause paired with governing law", "medium"))

    return make_output(rule_name, inp, findings, "Governing Law", "Governing Law")
