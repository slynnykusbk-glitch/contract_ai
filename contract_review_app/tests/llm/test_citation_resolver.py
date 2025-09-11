import pytest
from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.core.schemas import Finding, Span


def _f(code: str = "", rule: str = "", message: str = "") -> Finding:
    f = Finding(code=code, message=message, span=Span(start=0, length=1))
    if rule:
        object.__setattr__(f, "rule", rule)
    return f


@pytest.mark.parametrize(
    "finding,instrument,section",
    [
        (_f(code="uk_poca_tipping_off"), "POCA 2002", "s.333A"),
        (_f(rule="uk_ucta_liability"), "UCTA 1977", "s.2(1)"),
        (_f(code="ca1159"), "Companies Act 2006", "s.1159"),
        (_f(rule="ca1161"), "Companies Act 2006", "s.1161"),
        (_f(code="dpa_demo"), "DPA 2018", "Part 2"),
        (_f(code="gdpr_art_28"), "UK GDPR", "Art. 28"),
        (_f(message="adequate procedures and bribery"), "Bribery Act 2010", "s.7"),
    ],
)
def test_citation_resolver_new_presets(finding, instrument, section):
    cit = resolve_citation(finding)
    assert cit is not None
    assert cit.instrument == instrument
    assert cit.section == section
