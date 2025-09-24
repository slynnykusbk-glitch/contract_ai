import pytest
from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules.rules import termination as term


def test_termination_strong_clause_ok():
    text = """
    TERMINATION. Either party may terminate this Agreement for cause upon material breach
    by the other party, after providing 30 days' written notice and an opportunity to remedy.
    Termination may also occur for insolvency or bankruptcy of the other party.
    """
    out = term.analyze(AnalysisInput(clause_type="termination", text=text))
    assert out.status == "OK"
    assert out.score == 100
    assert out.risk_level == "low"
    assert not out.findings
    assert any("termination" in c.lower() for c in out.citations)


def test_termination_missing_elements_warn():
    text = """
    TERMINATION. Supplier may terminate this Agreement at any time.
    """
    out = term.analyze(AnalysisInput(clause_type="termination", text=text))
    assert out.status in ["WARN", "FAIL"]
    assert any("missing" in f.message.lower() for f in out.findings)


def test_termination_empty_clause_fail():
    out = term.analyze(AnalysisInput(clause_type="termination", text=""))
    assert out.status == "FAIL"
    assert out.score == 0
    assert any(d.severity == "critical" for d in out.diagnostics)
