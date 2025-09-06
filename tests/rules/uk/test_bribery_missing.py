from contract_review_app.legal_rules import loader


def _hit(text: str) -> bool:
    loader.load_rule_packs()
    findings = loader.match_text(text)
    return any(f["rule_id"] == "uk_bribery_act_missing" for f in findings)


def test_bribery_act_missing_detected():
    text = "Bribery is strictly prohibited and each party shall maintain policies."
    assert _hit(text)


def test_bribery_act_present_not_detected():
    text = "The parties shall comply with the UK Bribery Act 2010 and maintain anti-bribery policies."
    assert not _hit(text)
