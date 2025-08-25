from contract_review_app.legal_rules.loader import match_text, rules_count


def test_rules_count_positive():
    assert rules_count() > 0


def test_match_text_governing_law():
    text = "This Agreement is governed by the laws of England and Wales."
    findings = match_text(text)
    assert any(f.get("clause_type") == "governing_law" for f in findings)


def test_match_text_confidentiality():
    text = "Each party shall keep all confidential information confidential."
    findings = match_text(text)
    assert any(f.get("rule_id") == "confidentiality_basic" for f in findings)


def test_match_text_termination_notice():
    text = "Either party may terminate this agreement upon 30 days' written notice."
    findings = match_text(text)
    assert any(f.get("rule_id") == "termination_notice_basic" for f in findings)


def test_match_text_payment_terms():
    text = "Customer shall pay all invoices within 30 days of receipt."
    findings = match_text(text)
    assert any(f.get("rule_id") == "payment_terms_basic" for f in findings)

