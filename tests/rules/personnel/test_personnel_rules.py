import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput


def AI(text, clause="privacy", doc="MSA"):
    return AnalysisInput(clause_type=clause, text=text,
                         metadata={"jurisdiction": "UK", "doc_type": doc})


# --- 12 GDPR personnel data (updated) ---

def test_gdpr_negative_missing_bases():
    spec = load_rule("core/rules/universal/personnel/12_gdpr_personnel_data.yaml")
    t = (
        "The Contractor may process personal data of Personnel, including health data, "
        "for project administration purposes."
    )
    out = run_rule(spec, AI(t, "privacy"))
    # ожидаем флаги по Art.6 и Art.9
    assert out and any("Art.6" in f.message for f in out.findings)
    assert any("Art.9" in f.message for f in out.findings)


def test_gdpr_negative_no_dpia_on_large_scale():
    spec = load_rule("core/rules/universal/personnel/12_gdpr_personnel_data.yaml")
    t = (
        "The Contractor will conduct large-scale processing of personnel data for workforce analytics, "
        "with an explicit lawful basis (Art.6) and a stated special category condition (Art.9)."
    )
    out = run_rule(spec, AI(t, "privacy"))
    # базисы указаны, но DPIA не упомянут — ожидаем флаг
    assert out and any("DPIA" in f.message for f in out.findings)


def test_gdpr_positive_full():
    spec = load_rule("core/rules/universal/personnel/12_gdpr_personnel_data.yaml")
    t = (
        "Processing of Personnel data relies on an Art.6 lawful basis (legal obligation/contract). "
        "Any special category data (e.g., health/biometric) is processed under an Art.9 condition "
        "or a DPA 2018 Schedule 1 condition. A Data Protection Impact Assessment (DPIA) will be "
        "performed before any large-scale or systematic monitoring. The Contractor will apply "
        "data minimisation and maintain a retention schedule."
    )
    out = run_rule(spec, AI(t, "privacy"))
    assert not out or len(getattr(out, "findings", [])) == 0
