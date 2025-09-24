from contract_review_app.legal_rules import loader


def test_itp_hw_notice_single_comment():
    text = (
        "Contractor shall produce an inspection and test plan. "
        "The plan will list inspections only. No advance notice stated."
    )
    loader.load_rule_packs()
    findings = [
        f for f in loader.match_text(text) if f["rule_id"] == "quality.itp.hw_notice_5d"
    ]
    assert len(findings) == 1
    f = findings[0]
    assert f["scope"]["unit"] == "sentence"
    assert f["occurrences"] == 1


def test_no_ship_aggregation():
    text = "Contractor may ship the Goods without final inspection and may ship the Equipment without final inspection."
    loader.load_rule_packs()
    findings = [
        f
        for f in loader.match_text(text)
        if f["rule_id"] == "quality.no_ship_without_final_inspection"
    ]
    assert len(findings) == 1
    assert findings[0]["occurrences"] == 2
