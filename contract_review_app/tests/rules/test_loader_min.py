from contract_review_app.legal_rules.loader import match_text, rules_count


def test_rules_count_positive():
    assert rules_count() > 0


def test_match_text_governing_law():
    text = "This Agreement is governed by the laws of England and Wales."
    findings = match_text(text)
    assert any(f.get("clause_type") == "governing_law" for f in findings)

