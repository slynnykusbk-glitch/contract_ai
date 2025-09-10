from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules.rules import governing_law as gl

def test_glaw_empty_fail():
    out = gl.analyze(AnalysisInput(clause_type="governing_law", text=""))
    assert out.status == "FAIL"
    assert out.score == 35
    assert any(f.code in {"GLAW_EMPTY", "GLAW_MISSING"} for f in out.findings)

def test_glaw_strong_ew_ok():
    text = "This Agreement shall be governed by and construed in accordance with the laws of England and Wales."
    out = gl.analyze(AnalysisInput(clause_type="governing_law", text=text))
    assert out.status == "OK"
    assert out.score == 100
    assert out.risk_level == "low"
