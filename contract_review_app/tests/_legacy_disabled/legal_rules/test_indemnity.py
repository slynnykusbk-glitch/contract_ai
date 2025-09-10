import pytest
from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules.rules import indemnity as ind

def test_indemnity_strong_clause_ok():
    text = """
    INDEMNITY. The Supplier shall indemnify and hold harmless the Customer against all direct losses,
    damages, costs, and expenses arising from any breach of contract, negligence, wilful misconduct, or fraud,
    except where caused by the Customer’s own negligence. The Supplier shall notify the Customer of any indemnity claim
    within 10 days and shall cooperate fully in the defence of any such claim. The indemnity shall be subject to the
    limitations of liability set out in this Agreement.
    """
    out = ind.analyze(AnalysisInput(clause_type="indemnity", text=text))
    assert out.status == "OK"
    assert out.risk_level == "low"
    assert out.score >= 85
    assert not any(f.severity == "high" for f in out.findings)

def test_indemnity_weak_clause_warn():
    text = """
    The Supplier shall indemnify the Customer.
    """
    out = ind.analyze(AnalysisInput(clause_type="indemnity", text=text))
    assert out.status in ("WARN", "FAIL")
    assert out.score < 85
    assert any(f.severity in ("medium", "high") for f in out.findings)
