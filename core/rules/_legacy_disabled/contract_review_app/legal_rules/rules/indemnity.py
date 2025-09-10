# QUARANTINED: legacy Python rule (not loaded by engine). Kept for reference only.  # flake8: noqa
from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output

rule_name = "indemnity"


def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    if not re.search(r"\bindemnif(y|ication)\b|\bhold harmless\b", text, flags=re.I):
        findings.append(
            mk_finding("IND-ABSENT", "No indemnity obligation detected", "medium")
        )
        return make_output(rule_name, inp, findings, "Indemnity", "Indemnity")

    # Exclusions
    if not re.search(
        r"\b(except|excluding|save that)\b.*\b(negligence|gross negligence|wilful misconduct|fraud)\b",
        text,
        flags=re.I,
    ):
        findings.append(
            mk_finding(
                "IND-EXC",
                "No exclusions for gross negligence / wilful misconduct",
                "high",
            )
        )

    # Caps / limitations (hint)
    if not re.search(
        r"\b(cap|limit(ed)? to|liability cap|limitation(?:s)? of liability)\b",
        text,
        flags=re.I,
    ):
        findings.append(
            mk_finding(
                "IND-CAP", "No cap/limit reference for indemnity exposure", "high"
            )
        )

    out = make_output(rule_name, inp, findings, "Indemnity", "Indemnity")
    for f in out.findings:
        if f.code in {"IND-EXC", "IND-CAP"}:
            f.severity_level = "high"
    return out
