from __future__ import annotations

import re

from contract_review_app.legal_rules import loader


def test_filter_rules(monkeypatch):
    sample_rules = [
        {
            "id": "R1",
            "doc_types": ["NDA"],
            "requires_clause": [],
            "triggers": {"any": [re.compile("confidential", re.I)]},
        },
        {
            "id": "R2",
            "doc_types": ["MSA"],
            "requires_clause": ["Termination"],
            "triggers": {
                "all": [re.compile("term", re.I), re.compile("termination", re.I)]
            },
        },
        {
            "id": "R3",
            "doc_types": ["Any"],
            "requires_clause": [],
            "triggers": {"regex": [re.compile("noncompete", re.I)]},
        },
        {
            "id": "R4",
            "doc_types": ["msa"],
            "requires_clause": ["Payment"],
            "triggers": {"any": [re.compile("pay", re.I)]},
        },
    ]

    monkeypatch.setattr(loader, "_RULES", sample_rules)

    text = (
        "This Confidentiality clause explains the term and termination clause. "
        "Payment is due. A NonCompete clause applies."
    )
    res = loader.filter_rules(
        text, doc_type="MSA", clause_types=["Termination", "Payment"]
    )

    ids = {r["rule"]["id"] for r in res}
    assert ids == {"R2", "R3", "R4"}

    matches = {r["rule"]["id"]: r["matches"] for r in res}
    assert any(m.lower().startswith("term") for m in matches["R2"])
    assert any("noncompete" in m.lower() for m in matches["R3"])
    assert any("pay" in m.lower() for m in matches["R4"])


def test_filter_rules_preserves_newlines(monkeypatch):
    anchored_rule = [
        {
            "id": "R_line",
            "doc_types": ["Any"],
            "requires_clause": [],
            "triggers": {
                "regex": [re.compile(r"^2\. Second clause", re.I | re.MULTILINE)]
            },
        }
    ]

    monkeypatch.setattr(loader, "_RULES", anchored_rule)

    text = "1. First clause\n2. Second clause"
    res = loader.filter_rules(text, doc_type="MSA", clause_types=[])

    assert len(res) == 1
    assert res[0]["rule"]["id"] == "R_line"
    assert res[0]["matches"] == ["2. Second clause"]
