from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules.rules import jurisdiction as juris

def test_juris_empty_fail():
    out = juris.analyze(AnalysisInput(clause_type="jurisdiction", text=""))
    assert out.status == "FAIL"
    assert out.score == 35
    assert any(f.code in {"JURIS_EMPTY", "JURIS_MISSING"} for f in out.findings)

def test_juris_strong_ew_ok():
    txt = "The courts of England and Wales shall have exclusive jurisdiction to settle any dispute arising out of this Agreement."
    out = juris.analyze(AnalysisInput(clause_type="jurisdiction", text=txt))
    assert out.status == "OK"
    assert out.score == 100
    assert out.risk_level == "low"
    assert out.severity == "low"

def test_juris_uk_ambiguous_warn():
    txt = "The courts of the United Kingdom shall have jurisdiction."
    out = juris.analyze(AnalysisInput(clause_type="jurisdiction", text=txt))
    assert out.status == "WARN"
    assert any(f.code == "JURIS_UK_AMBIGUOUS" for f in out.findings)
