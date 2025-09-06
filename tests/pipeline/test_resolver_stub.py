from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.core.schemas import Finding, Span


def _f(code: str) -> Finding:
    return Finding(code=code, message="", span=Span(start=0, length=1))


def test_resolver_known_rules():
    cases = {
        "POCA": ("POCA 2002", "s.327"),
        "UCTA": ("UCTA 1977", "s.2"),
        "CompaniesAct": ("Companies Act 2006", "s.172"),
        "UKGDPR": ("UK GDPR", "Art. 5"),
    }
    for code, (instrument, section) in cases.items():
        cit = resolve_citation(_f(code))
        assert cit is not None
        assert cit.instrument == instrument
        assert cit.section == section
