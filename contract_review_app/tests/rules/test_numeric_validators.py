from contract_review_app.legal_rules.loader import (
    MONEY_RE,
    PERCENT_RE,
    carveouts_valid,
    match_text,
)


def _has(rule_id, findings):
    return any(f.get("rule_id") == rule_id for f in findings)


def test_liability_cap_placeholder():
    text = "The liability cap shall be [●]."
    findings = match_text(text)
    assert _has("liability_cap_placeholders", findings)


def test_pollution_cap_value_present():
    text = "The pollution cap is £5,000,000 per occurrence."
    findings = match_text(text)
    assert _has("pollution_cap_value_present", findings)


def test_property_damage_cap_value_present():
    text = "Property damage cap is €2,500,000 per occurrence."
    findings = match_text(text)
    assert _has("property_damage_cap_value_present", findings)


def test_insurance_requirements():
    text = (
        "Vendor shall name Company as an additional insured. "
        "Failure to comply shall result in termination."
    )
    findings = match_text(text)
    assert _has("insurance_additional_insureds_required", findings)
    assert _has("failure_to_comply_termination", findings)


def test_payment_terms_vat_present():
    text = "Invoices are payable within 30 days plus VAT of 20%."
    findings = match_text(text)
    assert _has("payment_terms_vat_present", findings)


def test_money_and_percent_regex():
    text = "Amounts: £5,000 and $3,200. Discount 10.5%."
    assert MONEY_RE.findall(text) == ["£5,000", "$3,200"]
    assert PERCENT_RE.findall(text) == ["10.5%"]


def test_carveouts_valid():
    assert carveouts_valid("fraud, gross negligence")
    assert not carveouts_valid("fraud, bad faith")
