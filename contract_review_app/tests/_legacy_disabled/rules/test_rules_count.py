from contract_review_app.legal_rules.loader import rules_count


def test_rules_count_minimum():
    assert rules_count() >= 6
