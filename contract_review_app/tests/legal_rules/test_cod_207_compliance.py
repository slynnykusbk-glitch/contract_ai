import pytest
from contract_review_app.legal_rules import loader

POSITIVE_CASES = [
    (
        "The parties shall comply with the Bribery Act 2010 and maintain adequate procedures; breach allows audit and termination.",
        "anti_bribery_ba2010",
    ),
    (
        "Each party will comply with UK, EU and US sanctions laws and will not perform for any sanctioned party.",
        "sanctions_screening",
    ),
    (
        "Supplier complies with the Modern Slavery Act and publishes an annual slavery statement.",
        "modern_slavery_statement",
    ),
    (
        "Processor complies with UK GDPR and the Data Protection Act 2018 and notifies breaches within 72 hours using Standard Contractual Clauses for transfers.",
        "data_protection_uk_gdpr",
    ),
    (
        "The goods are subject to HMRC oversight and dual-use export control.",
        "export_control_reiterated",
    ),
]

NEGATIVE_CASES = [
    ("No anti-bribery language here.", "anti_bribery_ba2010"),
    ("No sanctions clause.", "sanctions_screening"),
    ("No slavery obligations mentioned.", "modern_slavery_statement"),
    ("Generic privacy clause without UK terms.", "data_protection_uk_gdpr"),
    ("No shipping restrictions noted.", "export_control_reiterated"),
]


@pytest.mark.parametrize("text,rule_id", POSITIVE_CASES)
def test_compliance_rules_positive(text, rule_id):
    findings = loader.match_text(text)
    assert any(f["rule_id"] == rule_id for f in findings)
    match = next(f for f in findings if f["rule_id"] == rule_id)
    assert match["severity"] == "high"


@pytest.mark.parametrize("text,rule_id", NEGATIVE_CASES)
def test_compliance_rules_negative(text, rule_id):
    findings = loader.match_text(text)
    assert all(f["rule_id"] != rule_id for f in findings)
