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
    res = loader.filter_rules(text, doc_type="MSA", clause_types=["Termination", "Payment"])
    statuses = {r["rule"]["id"]: r.get("status") for r in res}
    assert statuses["R1"] == "doc_type_mismatch"

    matches = {r["rule"]["id"]: r.get("matches", []) for r in res if r.get("matches")}
    assert any(m.lower().startswith("term") for m in matches["R2"])
    assert any("noncompete" in m.lower() for m in matches["R3"])
    assert any("pay" in m.lower() for m in matches["R4"])
