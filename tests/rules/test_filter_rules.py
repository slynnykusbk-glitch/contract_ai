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
    sample_rules = [
        {
            "id": "R5",
            "doc_types": ["MSA"],
            "requires_clause": [],
            "triggers": {"regex": [re.compile(r"^second", re.I | re.MULTILINE)]},
        },
    ]

    monkeypatch.setattr(loader, "_RULES", sample_rules)

    text = "first line\nSecond line"
    res = loader.filter_rules(text, doc_type="MSA", clause_types=[])
    assert {r["rule"]["id"] for r in res} == {"R5"}
    assert any(m.lower().startswith("second") for m in res[0]["matches"])


def test_filter_rules_without_doc_type(monkeypatch):
    sample_rules = [
        {
            "id": "R6",
            "doc_types": ["NDA"],
            "requires_clause": [],
            "triggers": {"regex": [re.compile("nda", re.I)]},
        },
        {
            "id": "R7",
            "doc_types": ["Any"],
            "requires_clause": [],
            "triggers": {"regex": [re.compile("open", re.I)]},
        },
    ]

    monkeypatch.setattr(loader, "_RULES", sample_rules)

    text = "This OPEN section applies."
    res = loader.filter_rules(text, doc_type=None, clause_types=None)

    assert {r["rule"]["id"] for r in res} == {"R7"}
