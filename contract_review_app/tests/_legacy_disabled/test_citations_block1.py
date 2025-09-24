import pytest
from typing import Any
from pydantic import ValidationError
from hypothesis import given, strategies as st

from contract_review_app.core.schemas import Citation, Finding, AnalysisOutput


def test_citation_basic_valid():
    c = Citation(system="UK", instrument="Law", section="s1", url="https://example.com")
    assert c.system == "UK"
    assert c.instrument == "Law"
    assert c.section == "s1"
    assert str(c.url).startswith("https://example.com")


def test_citation_optional_fields_tolerated():
    data = {
        "system": "UK",
        "instrument": "Act",
        "section": "1",
        "url": "https://example.com",
        "title": "Example",
        "source": "Test",
        "link": "https://example.com/link",
        "score": 0.5,
        "evidence_text": "Evidence",
    }
    c = Citation(**data)
    for key, value in data.items():
        if key in {"system", "instrument", "section", "url"}:
            continue
        assert getattr(c, key, value if key == "score" else None) in {value, None}


def test_citation_evidence_backwards_compat():
    c_old = Citation(
        system="UK", instrument="Act", section="1", evidence_text="Old evidence"
    )
    assert c_old.evidence and c_old.evidence.text == "Old evidence"
    assert c_old.evidence_text == "Old evidence"

    c_new = Citation(
        system="UK",
        instrument="Act",
        section="1",
        evidence={
            "text": "New evidence",
            "source": "Source",
            "link": "https://example.com/evid",
        },
    )
    assert c_new.evidence and c_new.evidence.text == "New evidence"
    assert c_new.evidence.source == "Source"
    assert str(c_new.evidence.link).startswith("https://example.com/evid")
    assert c_new.evidence_text == "New evidence"


def test_citation_url_validation():
    with pytest.raises(ValidationError):
        Citation(system="UK", instrument="Law", section="1", url="not-a-url")


@pytest.mark.parametrize("score", [-1.0, 2.0])
def test_citation_score_bounds(score: float):
    data = {
        "system": "UK",
        "instrument": "Act",
        "section": "1",
        "score": score,
    }
    c = Citation(**data)
    val = getattr(c, "score", None)
    if val is not None:
        assert 0.0 <= val <= 1.0


def test_backward_compat_str_and_dict():
    f = Finding(code="X", message="m", citations="Law")
    assert len(f.citations) == 1
    assert f.citations[0].instrument == "Law"

    f2 = Finding(code="X", message="m", citations={"instrument": "Reg", "section": "s"})
    assert len(f2.citations) == 1
    assert f2.citations[0].instrument == "Reg"

    assert Finding(code="X", message="m", citations=None).citations == []


def test_findings_accept_evidence_object():
    f = Finding(
        code="X",
        message="m",
        citations=[{"instrument": "Act", "section": "s", "evidence": {"text": "E"}}],
    )
    assert f.citations and f.citations[0].evidence.text == "E"

    f2 = Finding(
        code="X",
        message="m",
        citations=[{"instrument": "Act", "section": "s", "evidence_text": "E"}],
    )
    assert f2.citations and f2.citations[0].evidence.text == "E"


def test_coerce_citations_mixed_and_invalid():
    mixed = [
        "plain",
        {"instrument": "Dict"},
        Citation(system="UK", instrument="Obj", section="s"),
        123,
    ]
    out = Finding._coerce_citations(mixed)
    assert isinstance(out, list)
    assert all(isinstance(c, Citation) for c in out)
    assert len(out) in {3, 4}


def test_integration_with_finding_and_analysis_output():
    cit = Citation(system="UK", instrument="Act", section="1")
    f = Finding(
        code="C",
        message="M",
        citations=["law", {"instrument": "Reg", "section": "s"}, cit],
    )
    assert all(isinstance(c, Citation) for c in f.citations)

    ao = AnalysisOutput(
        clause_type="demo",
        text="sample",
        status="OK",
        findings=[],
        citations=["law", {"instrument": "Reg", "section": "s"}, cit],
    )
    assert all(isinstance(c, Citation) for c in ao.citations)


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_property_score_clamped(random_score: float):
    c = Citation(system="UK", instrument="A", section="s", score=random_score)
    val = getattr(c, "score", None)
    if val is not None:
        assert 0.0 <= val <= 1.0


citation_dict_strategy = st.fixed_dictionaries(
    {
        "instrument": st.text(min_size=1),
        "section": st.text(min_size=1),
        "system": st.sampled_from(["UK", "EU", "UA", "INT"]),
    }
)

mixed_citation_strategy = st.one_of(
    st.text(min_size=1),
    citation_dict_strategy,
    st.builds(
        Citation,
        system=st.sampled_from(["UK", "EU", "UA", "INT"]),
        instrument=st.text(min_size=1),
        section=st.text(min_size=1),
    ),
    st.integers(),
)


@given(st.lists(mixed_citation_strategy))
def test_property_coerce_list(mixed_list):
    out = Finding._coerce_citations(mixed_list)
    assert isinstance(out, list)
    assert all(isinstance(c, Citation) for c in out)
