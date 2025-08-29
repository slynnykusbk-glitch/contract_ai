from __future__ import annotations
import re
from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from .base import mk_finding, make_output

rule_name = "governing_law"
RULE_NAME = rule_name

LAW_RE = r"(laws? of (england(?: and wales)?|scotland|northern ireland|united kingdom|uk))"

def analyze(inp: AnalysisInput) -> AnalysisOutput:
    text = inp.text or ""
    findings = []

    if not re.search(
        r"\bgoverning\s+law\b|\bthis\s+agreement\s+(?:is|shall\s+be)\s+governed\s+by\b",
        text,
        flags=re.I,
    ):
        has_law_words = re.search(r"law|прав", text, flags=re.I)
        has_jur_words = re.search(r"jurisdiction|court|суд", text, flags=re.I)
        if not text.strip():
            sev = "critical"
        elif has_law_words or has_jur_words:
            sev = "high"
        else:
            sev = "critical"
        msg = "No explicit governing law statement"
        if has_law_words:
            msg += " (без явного застосовного права)"
        elif has_jur_words:
            msg += " (не вдалося однозначно ідентифікувати)"
        else:
            msg += " (відсутня або неявна)"
        findings.append(mk_finding("GLAW_MISSING", msg, sev))
    else:
        if not re.search(LAW_RE, text, flags=re.I):
            findings.append(
                mk_finding(
                    "GL-JUR",
                    "Governing law lacks specific jurisdiction (e.g., 'laws of England and Wales')",
                    "high",
                )
            )
        else:
            findings.append(mk_finding("GLAW_REF", "посилання на право визначено", "info"))
        # Jurisdiction clause is optional; no finding if absent

    out = make_output(rule_name, inp, findings, "Governing Law", "Governing Law")
    if any(f.get("code") == "GLAW_MISSING" for f in findings):
        out.recommendations.append("Add explicit governing law clause.")
    return out
