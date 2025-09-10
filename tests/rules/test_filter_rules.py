from __future__ import annotations

import re

from contract_review_app.legal_rules import loader


def test_filter_rules(monkeypatch):
    sample_rules = [
        {
            "id": "R1",
            "doc_types": ["NDA"],
            "requires_clause": [],
            "triggers": {"any": [re.compile("confidential", re.I | re.MULTILINE)]},
        },
        {
            "id": "R2",
            "doc_types": ["MSA"],
            "requires_clause": ["Termination"],
            "triggers": {
                "all": [
                    re.compile("term", re.I | re.MULTILINE),
                    re.compile("termination", re.I | re.MULTILINE),
                ]
            },
        },
        {
            "id": "R3",
            "doc_types": ["Any"],
            "requires_clause": [],
            "triggers": {"regex": [re.compile("noncompete", re.I | re.MULTILINE)]},
        },
        {
            "id": "R4",
            "doc_types": ["msa"],
            "requires_clause": ["Payment"],
            "triggers": {"any": [re.compile("pay", re.I | re.MULTILINE)]},
        },
    ]

    # подменяем загруженные правила
    monkeypatch.setattr(loader, "_RULES", sample_rules)

    text = (
        "This Confidentiality clause explains the term and termination clause. "
        "Payment is due. A NonCompete clause applies."
    )

    filtered, coverage = loader.filter_rules(
        text, doc_type="MSA", clause_types=["Termination", "Payment"]
    )

    ids = {r["rule"]["id"] for r in filtered}
    assert ids == {"R2", "R3", "R4"}

    matches = {r["rule"]["id"]: r["matches"] for r in filtered}
    assert any(m.lower().startswith("term") for m in matches["R2"])
    assert any("noncompete" in m.lower() for m in matches["R3"])
    assert any("pay" in m.lower() for m in matches["R4"])

    cov_map = {c["rule_id"]: c for c in coverage}
    assert len(coverage) == 4
    assert cov_map["R1"]["flags"] & loader.DOC_TYPE_MISMATCH
    assert cov_map["R2"]["flags"] & loader.FIRED


def test_filter_rules_preserves_newlines(monkeypatch):
    anchored_rule = [
        {
            "id": "R_line",
            "doc_types": ["Any"],
            "requires_clause": [],
            "triggers": {
                # якорим по началу строки — важно сохранить \n при нормализации
                "regex": [re.compile(r"^2\. Second clause", re.I | re.MULTILINE)]
            },
        }
    ]

    monkeypatch.setattr(loader, "_RULES", anchored_rule)

    text = "1. First clause\n2. Second clause"
    filtered, coverage = loader.filter_rules(text, doc_type="MSA", clause_types=[])

    assert [r["rule"]["id"] for r in filtered] == ["R_line"]
    assert filtered[0]["matches"] == ["2. Second clause"]
    # убедимся, что есть спаны и флаг FIRED
    cov = coverage[0]
    assert cov["flags"] & loader.FIRED
    assert cov["spans"] and cov["spans"][0]["start"] < cov["spans"][0]["end"]
