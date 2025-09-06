from contract_review_app.legal_rules import loader


def _hit(text: str) -> bool:
    loader.load_rule_packs()
    findings = loader.match_text(text)
    return any(f["rule_id"] == "uk_poca_tipping_off" for f in findings)


def test_poca_tipping_off_detects_missing_carveout():
    text = "The Parties shall keep all information confidential and shall not disclose it to any person."
    assert _hit(text)


def test_poca_tipping_off_not_triggered_with_carveout():
    text = (
        "The Parties shall keep all information confidential and shall not disclose it to any person except as required by law or by a regulator."
    )
    assert not _hit(text)
