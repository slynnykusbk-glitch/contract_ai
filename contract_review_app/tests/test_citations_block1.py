from hypothesis import given, strategies as st

from contract_review_app.core.schemas import Citation, Finding, AnalysisOutput, Evidence, TextSpan


def test_citation_basic_valid():
    evid = Evidence(text="Evidence", spans=[TextSpan(start=0, end=7, lang="en", script="Latn")])
    c = Citation(title="Law", source_type="law", source_id="s1", evidence=[evid], score=0.5, meta={"url": "https://example.com"})
    assert c.title == "Law"
    assert c.source_type == "law"
    assert c.source_id == "s1"
    assert c.evidence and c.evidence[0].spans[0].start == 0
    assert c.meta["url"].startswith("https://example.com")


def test_citation_score_bounds():
    c = Citation(title="A", score=2.0)
    assert c.score == 1.0
    c2 = Citation(title="B", score=-0.5)
    assert c2.score == 0.0


def test_backward_compat_str_and_dict():
    f = Finding(code="X", message="m", citations="Law")
    assert f.citations and f.citations[0].title == "Law"

    f2 = Finding(code="X", message="m", citations={"title": "Reg", "source_type": "law"})
    assert f2.citations and f2.citations[0].title == "Reg"

    assert Finding(code="X", message="m", citations=None).citations == []


def test_coerce_citations_mixed_and_invalid():
    mixed = [
        "plain",
        {"title": "Dict"},
        Citation(title="Obj"),
        123,
    ]
    out = Finding._coerce_citations(mixed)
    assert isinstance(out, list)
    assert all(isinstance(c, Citation) for c in out)
    assert len(out) in {3, 4}


def test_integration_with_finding_and_analysis_output():
    cit = Citation(title="Act", source_type="law")
    f = Finding(code="C", message="M", citations=["law", {"title": "Reg"}, cit])
    assert all(isinstance(c, Citation) for c in f.citations)

    ao = AnalysisOutput(
        clause_type="demo",
        text="sample",
        status="OK",
        findings=[],
        citations=["law", {"title": "Reg"}, cit],
    )
    assert all(isinstance(c, Citation) for c in ao.citations)


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_property_score_clamped(random_score: float):
    c = Citation(title="A", score=random_score)
    val = getattr(c, "score", None)
    if val is not None:
        assert 0.0 <= val <= 1.0


citation_dict_strategy = st.fixed_dictionaries({"title": st.text(min_size=1)})

mixed_citation_strategy = st.one_of(
    st.text(min_size=1),
    citation_dict_strategy,
    st.builds(Citation, title=st.text(min_size=1)),
    st.integers(),
)


@given(st.lists(mixed_citation_strategy))
def test_property_coerce_list(mixed_list):
    out = Finding._coerce_citations(mixed_list)
    assert isinstance(out, list)
    assert all(isinstance(c, Citation) for c in out)
