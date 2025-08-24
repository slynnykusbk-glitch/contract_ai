from __future__ import annotations

from contract_review_app.intake.adapters import normalize_for_rules
from contract_review_app.core.schemas import AnalysisInput


def test_normalize_for_rules_basic_and_ordering():
    data = {
        "Payment": "  Payment shall be due within 30 days. ",
        "definitions": "In this Agreement, “Fees” shall mean …",
        "TERMINATION": "This Agreement may be terminated for material breach.",
        "": "should be ignored",
    }
    out = normalize_for_rules(data, doc_id="DOC-1")
    assert [x.clause_type for x in out] == ["definitions", "payment", "termination"]
    assert all(isinstance(x, AnalysisInput) for x in out)
    assert all(x.text and x.text == x.text.strip() for x in out)

    for i, x in enumerate(out):
        assert x.metadata.get("index") == str(i)
        assert int(x.metadata.get("len", "0")) > 0
        assert int(x.metadata.get("char_count", "0")) >= len(x.text)
        assert x.metadata.get("doc_id") == "DOC-1"
        assert x.metadata.get("source") == "intake.extractor"


def test_normalize_for_rules_filters_empty_or_invalid():
    out = normalize_for_rules({"": "", "x": ""})
    assert out == []
