from contract_review_app.legal_rules import loader


def test_ucta_2_1_invalid_triggers():
    text = "The Supplier excludes liability for death or personal injury caused by negligence."
    loader.load_rule_packs()
    findings = loader.match_text(text)
    assert any(f["rule_id"] == "uk_ucta_2_1_invalid" for f in findings)
