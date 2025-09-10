import pytest
from contract_review_app.retrieval.highlight import make_snippet


def test_make_snippet_includes_keyword_and_ellipsis():
    text = "A" * 100 + "principles" + "B" * 100
    query = "principles processing"
    snippet = make_snippet(text, query, window=10)
    assert "principles" in snippet.lower()
    assert snippet.startswith("…") and snippet.endswith("…")


def test_make_snippet_deterministic():
    text = "Data processing principles are important."
    query = "processing"
    s1 = make_snippet(text, query)
    s2 = make_snippet(text, query)
    assert s1 == s2
