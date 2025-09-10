from contract_review_app.legal_rules import loader


def test_rule_audit_mode(api):
    r = api.post("/api/analyze?debug=coverage", json={"text": "Hello"})
    assert r.status_code == 200
    data = r.json()
    coverage = data.get("rules_coverage")
    assert isinstance(coverage, list)
    assert len(coverage) == loader.rules_count()

    sample = coverage[0]
    assert {
        "doc_type",
        "pack_id",
        "rule_id",
        "severity",
        "evidence",
        "spans",
        "flags",
    } <= set(sample)

    assert any(c["flags"] & loader.DOC_TYPE_MISMATCH for c in coverage)
