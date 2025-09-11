from contract_review_app.legal_rules import loader

SAMPLE_TEXT = (
    'This Non-Disclosure Agreement is made between BlackRock Holdings Limited (Company Number 123456, registered at 20 Bank Street, London) ("Discloser") and BlackRock Holdings Limited (Company Number 654321, registered at 25 Bank Street, London) ("Recipient").\n'
    "Purpose. Recipient shall use the Confidential Information for any purpose whatsoever.\n"
    "Payment. Recipient shall pay Discloser £1,500,000 upon execution.\n"
    "Confidentiality Exceptions. Information already in the public domain is excluded. Information illegally in the possession of Recipient is also excluded.\n"
    "Liability. Recipient shall not be liable for any damages even in case of fraud.\n"
    "Regulatory. Recipient shall not notify any regulator without prior consent, but nevertheless Recipient shall notify the FCA within 24 hours.\n"
    "Governing Law. This Agreement is governed by the laws of England and the courts of New York shall have exclusive jurisdiction.\n"
    "Miscellaneous. References to Companies Act 1985 are included herein."
)

ROOTS = [
    "core/rules/uk/nda_basics",
    "core/rules/uk/company_ident",
    "core/rules/uk_regulatory",
    "core/rules/uk_privacy",
    "core/rules/uk_drafting_sanity",
]

EXPECTED_RULES = {
    "uk_company_name_number_mismatch",
    "uk_company_address_conflict",
    "uk_ndabasic_broad_purpose",
    "uk_ndabasic_unexpected_payment",
    "uk_privacy_public_domain_exception",
    "uk_privacy_illegal_possession_exception",
    "uk_drafting_no_fraud_exception",
    "uk_regulatory_prohibited_notice",
    "uk_drafting_outdated_companies_act",
    "uk_drafting_law_forum_mismatch",
}


def test_blackrock_nda_sample():
    loader.load_rule_packs(roots=ROOTS)
    filtered, coverage = loader.filter_rules(
        SAMPLE_TEXT, doc_type="nda", clause_types=[]
    )
    ids = {r["rule"]["id"] for r in filtered}
    assert EXPECTED_RULES <= ids

    assert len(coverage) == len(EXPECTED_RULES)
    fired = sum(1 for c in coverage if c["flags"] & loader.FIRED)
    assert fired == len(EXPECTED_RULES)
    assert len(filtered) == len(EXPECTED_RULES)
