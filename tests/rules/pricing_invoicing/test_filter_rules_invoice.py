from contract_review_app.legal_rules import loader


def test_invoice_rule_excluded_without_invoice_clause():
    text = "The parties agree to keep all information confidential and return materials upon request."
    loader.load_rule_packs()
    res = loader.filter_rules(text, doc_type="NDA", clause_types=["confidentiality"])
    ids = {r["rule"]["id"] for r in res}
    assert "P2.INVOICE_CONTENT_VAT" not in ids


def test_invoice_rule_triggers_with_required_clause():
    text = (
        "Invoice must include VAT and reference the PO and GRN for payment processing."
    )
    loader.load_rule_packs()
    res = loader.filter_rules(text, doc_type="MSA", clause_types=["invoice"])
    fired_rules = {r["rule"]["id"]: r["matches"] for r in res}
    assert "P2.INVOICE_CONTENT_VAT" in fired_rules
    matches = fired_rules["P2.INVOICE_CONTENT_VAT"]
    assert any("vat" in m.lower() for m in matches)
    assert any("po" in m.lower() or "grn" in m.lower() for m in matches)
