from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.core.schemas import Finding


def test_resolve_citation_personal_data_message():
    finding = Finding(
        code="rule1", message="This clause mentions personal data processing."
    )
    result = resolve_citation(finding)
    assert result is not None
    citation = result[0]
    assert citation.instrument == "UK GDPR"
    assert citation.section == "Art. 28(3)"
    assert citation.title
    assert citation.source
    assert citation.score is not None
    assert citation.evidence_text


def test_resolve_citation_conf_gdpr_code():
    finding = Finding(code="conf_gdpr_check", message="No personal terms")
    result = resolve_citation(finding)
    assert result is not None
    citation = result[0]
    assert citation.instrument == "UK GDPR"
    assert citation.section == "Art. 28(3)"
    assert citation.title
    assert citation.source
    assert citation.score is not None
    assert citation.evidence_text


def test_resolve_citation_oguk_keyword():
    finding = Finding(code="rule2", message="OGUK standards for oil exploration apply.")
    result = resolve_citation(finding)
    assert result is not None
    citation = result[0]
    assert citation.instrument == "OGUK Model Agreement"
    assert citation.section == "General reference"
    assert citation.title == "OGUK Model Agreement for Offshore Operations"
    assert citation.source == "oguk.org.uk"
    assert citation.score == 1.0
    assert citation.evidence_text


def test_resolve_citation_unmatched_rule_code():
    """An unmatched rule code should yield no citation."""
    finding = Finding(code="conf_gdp_check", message="No personal terms")
    assert resolve_citation(finding) is None


def test_resolve_citation_no_match():
    finding = Finding(code="rule3", message="No special terms here.")
    assert resolve_citation(finding) is None
