from __future__ import annotations

import re

from contract_review_app.legal_rules import loader


def test_generic_rule_bypasses_scope(monkeypatch):
    rules = [
        {
            "id": "GEN",
            "doc_types": ["nda"],
            "jurisdiction": ["us"],
            "triggers": {"any": [re.compile("always", re.I | re.MULTILINE)]},
            "generic": True,
        },
        {
            "id": "SCOPED",
            "doc_types": ["nda"],
            "jurisdiction": ["us"],
            "triggers": {"any": [re.compile("scoped", re.I | re.MULTILINE)]},
        },
    ]

    monkeypatch.setattr(loader, "_RULES", rules)

    text = "Generic always applies while scoped needs matches"

    filtered, coverage = loader.filter_rules(
        text,
        doc_type="msa",
        clause_types=[],
        jurisdiction="uk",
    )

    fired_ids = {r["rule"]["id"] for r in filtered}
    assert fired_ids == {"GEN"}

    coverage_map = {c["rule_id"]: c for c in coverage}

    # generic правило должно сработать без mismatch-флагов
    assert coverage_map["GEN"]["flags"] & loader.FIRED
    assert not (coverage_map["GEN"]["flags"] & loader.DOC_TYPE_MISMATCH)
    assert not (coverage_map["GEN"]["flags"] & loader.JURISDICTION_MISMATCH)

    # обычное правило получает mismatch по doc_type и jurisdiction
    scoped_flags = coverage_map["SCOPED"]["flags"]
    assert scoped_flags & loader.DOC_TYPE_MISMATCH
    assert scoped_flags & loader.JURISDICTION_MISMATCH
