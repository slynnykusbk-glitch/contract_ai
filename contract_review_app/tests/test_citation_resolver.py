from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.core.schemas import Finding


def test_resolve_citation_personal_data_message():
    finding = Finding(
        code="rule1", message="This clause mentions personal data processing."
    )
    result = resolve_citation(finding)
    assert result is not None
    assert result[0].instrument == "UK GDPR"
    assert result[0].section == "Art. 28(3)"


def test_resolve_citation_conf_gdpr_code():
    finding = Finding(code="conf_gdpr_check", message="No personal terms")
    result = resolve_citation(finding)
    assert result is not None
    assert result[0].instrument == "UK GDPR"


def test_resolve_citation_oguk_keyword():
    finding = Finding(code="rule2", message="OGUK standards for oil exploration apply.")
    result = resolve_citation(finding)
    assert result is not None
    assert result[0].instrument == "OGUK Model Agreement"


def test_resolve_citation_no_match():
    finding = Finding(code="rule3", message="No special terms here.")
    assert resolve_citation(finding) is None
