from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.core.schemas import Finding, Span


def _f(code: str) -> Finding:
    return Finding(code=code, message="", span=Span(start=0, length=1))


def test_resolver_known_rules():
    cases = {
        "POCA": ("POCA 2002", "s.333A"),
        "UCTA": ("UCTA 1977", "s.2(1)"),
        "CompaniesAct": ("Companies Act 2006", "s.1159"),
        "CA1161": ("Companies Act 2006", "s.1161"),
        "UKGDPR": ("UK GDPR", "Art. 28"),
        "DPA": ("DPA 2018", "Part 2"),
        "Bribery": ("Bribery Act 2010", "s.7"),
    }
    for code, (instrument, section) in cases.items():
        cit = resolve_citation(_f(code))
        assert cit is not None
        assert cit.instrument == instrument
        assert cit.section == section
