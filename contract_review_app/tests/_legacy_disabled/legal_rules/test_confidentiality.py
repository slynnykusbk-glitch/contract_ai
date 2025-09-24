# tests/test_rule_confidentiality.py
from contract_review_app.legal_rules.rules import confidentiality as conf
from contract_review_app.core.schemas import AnalysisInput


def test_empty_clause_yields_findings_and_warn():
    out = conf.analyze(AnalysisInput(clause_type="confidentiality", text=""))
    assert any(f.code == "CONF-0" for f in out.findings)
    assert out.score < 100
    assert out.risk in {"medium", "high", "critical"}


def test_minimal_good_confidentiality_passes():
    text = (
        "Confidential Information means all information disclosed. "
        "Obligations survive termination. "
        "During the term and for 3 years after termination each party shall keep information confidential; "
        "return or destroy materials on request; "
        "disclosure to advisers and affiliates is permitted on need-to-know; "
        "exclusions include public domain, prior knowledge, independently developed, and disclosures required by law; "
        "injunctive relief may be sought."
    )
    out = conf.analyze(AnalysisInput(clause_type="confidentiality", text=text))
    # Should have 0-2 minor hints at most (e.g., GDPR hint if no PD)
    assert (
        all(f.severity_level in {"minor"} for f in out.findings)
        or len(out.findings) == 0
    )
    assert out.score >= 70
    assert out.risk in {"low", "medium"}


def test_personal_data_triggers_gdpr_hint():
    text = "The parties may process personal data and must keep such data confidential."
    out = conf.analyze(AnalysisInput(clause_type="confidentiality", text=text))
    codes = [f.code for f in out.findings]
    assert "CONF-9" in codes
    assert any(
        c.instrument.startswith("UK GDPR") for f in out.findings for c in f.citations
    )
