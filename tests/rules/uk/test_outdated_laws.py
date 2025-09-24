from contract_review_app.legal_rules import loader


def _hit(rule_id: str, text: str) -> bool:
    loader.load_rule_packs()
    findings = loader.match_text(text)
    return any(f["rule_id"] == rule_id for f in findings)


def test_companies_act_1985_flag():
    assert _hit("uk_ca_1985_outdated", "Reference is made to the Companies Act 1985.")


def test_dpa_1998_flag():
    assert _hit(
        "uk_dpa_1998_outdated",
        "The Supplier complies with the Data Protection Act 1998.",
    )
