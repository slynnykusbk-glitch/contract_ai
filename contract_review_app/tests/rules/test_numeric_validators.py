from contract_review_app.legal_rules.loader import match_text, rules_count


def _has(findings, rule_id):
    return any(f.get("rule_id") == rule_id for f in findings)


def test_rules_count_new_rules():
    assert rules_count() >= 6


def test_insurance_limits_min():
    bad = (
        "Employers' Liability £5,000,000 and Public Liability £1,000,000 "
        "professional services with Professional Indemnity £1,000,000."
    )
    good = (
        "Employers' Liability £10,000,000 and Public Liability £5,000,000 "
        "professional services with Professional Indemnity £2,000,000."
    )
    assert _has(match_text(bad), "insurance_limits_min")
    assert not _has(match_text(good), "insurance_limits_min")


def test_pollution_cap_present():
    bad = "Pollution liability cap: TBD."
    good = "Pollution liability cap: £1,000,000."
    assert _has(match_text(bad), "pollution_cap_present")
    assert not _has(match_text(good), "pollution_cap_present")


def test_property_damage_cap_present():
    bad = "Property damage cap: XX."
    good = "Property damage cap: £500,000."
    assert _has(match_text(bad), "property_damage_cap_present")
    assert not _has(match_text(good), "property_damage_cap_present")


def test_service_credits_if_sla():
    bad = "The SLA requires uptime of 99%."
    good = (
        "The SLA requires uptime of 99% and service credits will apply. "
        "Liquidated damages are included."
    )
    assert _has(match_text(bad), "service_credits_lds_present_if_sla")
    assert not _has(match_text(good), "service_credits_lds_present_if_sla")


def test_payment_terms_days():
    bad = "Payment terms: Net 60 days upon receipt of invoice."
    good = "Payment terms: Net 30 days upon receipt of a valid VAT invoice."
    assert _has(match_text(bad), "payment_terms_days")
    assert not _has(match_text(good), "payment_terms_days")
