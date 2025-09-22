import re

from contract_review_app.legal_rules import loader


def _make_rule(applies_labels=None, applies_segment_kind=None):
    rule = {
        "id": "payment-rule",
        "doc_types": ["any"],
        "requires_clause": [],
        "triggers": {"regex": [re.compile(r"payment", re.I | re.MULTILINE)]},
    }
    applies: dict[str, list[str]] = {}
    if applies_labels:
        applies["labels"] = applies_labels
    if applies_segment_kind:
        applies["segment_kind"] = applies_segment_kind
    if applies:
        rule["applies_to"] = applies
    return rule


def test_rule_fires_with_matching_labels(monkeypatch):
    sample_rule = _make_rule(applies_labels=["payment_terms"])
    monkeypatch.setattr(loader, "_RULES", [sample_rule])

    filtered, coverage = loader.filter_rules(
        "Payment terms shall apply.",
        doc_type="MSA",
        clause_types=[],
        segment_labels={"payment_terms"},
        segment_kind="clause",
    )

    assert [item["rule"]["id"] for item in filtered] == ["payment-rule"]
    assert coverage and coverage[0]["flags"] & loader.FIRED


def test_rule_blocked_without_labels(monkeypatch):
    sample_rule = _make_rule(applies_labels=["payment_terms"])
    monkeypatch.setattr(loader, "_RULES", [sample_rule])

    filtered, coverage = loader.filter_rules(
        "Payment terms shall apply.",
        doc_type="MSA",
        clause_types=[],
        segment_labels=set(),
        segment_kind="clause",
    )

    assert filtered == []
    assert coverage and coverage[0]["flags"] & loader.SEGMENT_LABEL_MISMATCH


def test_rule_blocked_by_segment_kind(monkeypatch):
    sample_rule = _make_rule(
        applies_labels=["payment_terms"], applies_segment_kind=["clause"]
    )
    monkeypatch.setattr(loader, "_RULES", [sample_rule])

    filtered, coverage = loader.filter_rules(
        "Payment terms shall apply.",
        doc_type="MSA",
        clause_types=[],
        segment_labels={"payment_terms"},
        segment_kind="schedule",
    )

    assert filtered == []
    assert coverage and coverage[0]["flags"] & loader.SEGMENT_KIND_MISMATCH
