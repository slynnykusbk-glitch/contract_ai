from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.legal_rules.rules import force_majeure as fm


def test_fm_missing_clause_fail():
    inp = AnalysisInput(
        clause_type="force_majeure",
        text="This agreement sets out the obligations of the parties.",
    )
    out = fm.analyze(inp)
    assert out.status == "FAIL"
    assert out.score == 35
    assert any(f.code == "FM_MISSING" for f in out.findings)


def test_fm_strong_clause_ok():
    text = """
    FORCE MAJEURE. Neither Party shall be liable for any failure caused by events beyond its reasonable control,
    including without limitation war, epidemic or pandemic, governmental orders, fire, flood, natural disaster,
    or acts of terrorism. The affected Party shall notify the other Party as soon as practicable and in any case
    within 7 days of becoming aware of the event. Each Party shall use reasonable efforts to mitigate the effects
    of the event. If the event continues for more than 60 days, either Party may terminate this Agreement upon notice.
    """
    out = fm.analyze(AnalysisInput(clause_type="force_majeure", text=text))
    assert out.status == "OK"
    assert out.score == 100
    assert out.risk_level == "low"
    assert out.severity == "low"
