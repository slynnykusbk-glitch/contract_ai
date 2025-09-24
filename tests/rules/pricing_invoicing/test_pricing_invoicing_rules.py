import pytest
from contract_review_app.legal_rules import loader


def _find(rule_id: str, text: str):
    loader.load_rule_packs()
    findings = [f for f in loader.match_text(text) if f["rule_id"] == rule_id]
    assert len(findings) <= 1, f"duplicate findings for {rule_id}"
    return findings[0] if findings else None


def _common_checks(f):
    assert f is not None
    assert f.get("advice")
    assert isinstance(f.get("law_refs"), list) and f["law_refs"]
    scope = f.get("scope", {})
    assert scope.get("unit") in {"sentence", "subclause"}
    assert isinstance(f.get("occurrences"), int) and f["occurrences"] >= 1
    return f


def test_all_inclusive_rates():
    text = (
        "Rates are all-inclusive; no additional charges shall be payable unless listed."
    )
    f = _common_checks(_find("P1.ALL_INCLUSIVE_RATES", text))
    assert f["severity"] == "medium"


def test_invoice_vat_requirements():
    text = "Invoices must include VAT requirements and reference the PO and GRN. Records kept six years."
    f = _common_checks(_find("P2.INVOICE_CONTENT_VAT", text))
    assert f["severity"] == "high"


def test_late_invoice_timebar_flag():
    text = (
        "No payment for invoices submitted later than ninety (90) days after delivery."
    )
    f = _common_checks(_find("P3.LATE_INVOICE_TIMEBAR", text))
    assert f["severity"] == "high"
    assert "manual_review" in f.get("ops", [])


def test_payment_terms_and_interest():
    text = "Payment term is thirty (30) days from receipt; interest on late payment shall apply."
    f = _common_checks(_find("P4.PAYMENT_TERMS_AND_INTEREST", text))
    assert f["severity"] == "high"


def test_public_30days_cascade():
    text = "The contracting authority shall pay within 30 days under Reg 113 cascading to all subcontractors."
    f = _common_checks(_find("P5.PUBLIC_30DAYS_CASCADE", text))
    assert f["severity"] == "high"
    assert "public_sector" in f.get("ops", [])


def test_construction_pay_notices():
    text = "Pay-less notice shall comply with the Construction Act HGCRA."
    f = _common_checks(_find("P6.CONSTRUCTION_PAY_NOTICES", text))
    assert f["severity"] == "critical"
    assert "construction" in f.get("ops", [])


def test_setoff_scope_asymmetry():
    text = "Customer may set off or withhold amounts due."
    f = _common_checks(_find("P7.SETOFF_SCOPE", text))
    assert f["severity"] == "medium"


def test_pay_undisputed_portion():
    text = "Customer will pay the undisputed portion promptly while resolving disputes."
    f = _common_checks(_find("P8.PAY_UNDISPUTED", text))
    assert f["severity"] == "medium"


def test_einvoice_platform_vat_control():
    text = "Electronic invoices via SAP Business Network with 3-way match and records retained for six years."
    f = _common_checks(_find("P9.EINVOICE_PLATFORM_VAT_CONTROL", text))
    assert f["severity"] == "high"


def test_reimbursables_net_of_rebates():
    text = "Reimbursable costs are net of rebates and pass-through discounts."
    f = _common_checks(_find("P10.REIMBURSABLES_NET_OF_REBATES", text))
    assert f["severity"] == "medium"


def test_no_pay_idle_efficiency():
    text = "No payment for idle standby due to contractor fault and efficiency adjustment will apply."
    f = _common_checks(_find("P11.NO_PAY_IDLE_EFFICIENCY", text))
    assert f["severity"] == "high"


def test_receivables_assignment_permitted():
    text = "Supplier may not assign amounts due without consent."
    f = _common_checks(_find("P12.RECEIVABLES_ASSIGNMENT_PERMITTED", text))
    assert f["severity"] == "high"


def test_negative_cases():
    neutral = "The parties shall cooperate to deliver the project."
    loader.load_rule_packs()
    ids = {f["rule_id"] for f in loader.match_text(neutral)}
    for rid in [
        "P1.ALL_INCLUSIVE_RATES",
        "P2.INVOICE_CONTENT_VAT",
        "P3.LATE_INVOICE_TIMEBAR",
        "P4.PAYMENT_TERMS_AND_INTEREST",
        "P5.PUBLIC_30DAYS_CASCADE",
        "P6.CONSTRUCTION_PAY_NOTICES",
        "P7.SETOFF_SCOPE",
        "P8.PAY_UNDISPUTED",
        "P9.EINVOICE_PLATFORM_VAT_CONTROL",
        "P10.REIMBURSABLES_NET_OF_REBATES",
        "P11.NO_PAY_IDLE_EFFICIENCY",
        "P12.RECEIVABLES_ASSIGNMENT_PERMITTED",
    ]:
        assert rid not in ids
