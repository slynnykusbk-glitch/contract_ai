from core.engine.runner import load_rule, run_rule
from core.schemas import AnalysisInput

AI = lambda text, clause: AnalysisInput(text=text, clause_type=clause)

# --- prior written consent ---
def test_subcontracts_prior_consent_negative():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.prior_consent")
    t = "The Contractor may subcontract any portion of the Services."
    out = run_rule(spec, AI(t, "subcontracts"))
    assert out and any("prior written consent" in f.message.lower() for f in out.findings)

def test_subcontracts_prior_consent_positive():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.prior_consent")
    t = "Contractor shall not subcontract (including critical suppliers and sub-tiers) without Company’s prior written consent."
    out = run_rule(spec, AI(t, "subcontracts"))
    assert not out or len(out.findings) == 0

# --- flowdown minimum set ---
def test_flowdown_negative_missing_all():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.flowdown_minimum_set")
    t = "Contractor may appoint subcontractors."
    out = run_rule(spec, AI(t, "subcontracts"))
    msgs = " ".join(f.message for f in out.findings)
    assert "anti-bribery" in msgs.lower()
    assert "sanctions" in msgs.lower()
    assert "confidentiality" in msgs.lower() or "ip" in msgs.lower() or "audit" in msgs.lower()

def test_flowdown_positive_all_present():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.flowdown_minimum_set")
    t = ("Subcontractors shall comply with anti-bribery (Bribery Act), sanctions and export control (incl. ownership and control test), "
         "confidentiality and IP parity, insurance limits, audit and records retention.")
    out = run_rule(spec, AI(t, "subcontracts"))
    assert not out or len(out.findings) == 0

# --- Art.28 processor terms when subs process personal data ---
def test_art28_negative_missing_terms():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.data_protection_art28")
    t = "A subcontractor will process personal data for HR analytics."
    out = run_rule(spec, AI(t, "data protection"))
    assert out and any("Art.28" in " ".join(f.legal_basis) for f in out.findings)

def test_art28_positive_all_terms_present():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.data_protection_art28")
    t = ("A sub-processor may process personal data subject to Article 28 processor terms: controller instructions, security, audit/inspection, "
         "prior authorisation of sub-processors, and return/erase on termination.")
    out = run_rule(spec, AI(t, "data protection"))
    assert not out or len(out.findings) == 0

# --- ban pay-when-paid ---
def test_pay_when_paid_flag():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.ban_pay_when_paid")
    t = "Subcontractor shall be paid when paid by the Employer (pay-when-paid)."
    out = run_rule(spec, AI(t, "payments"))
    assert out and any("pay-when-paid" in f.message.lower() for f in out.findings)

def test_no_pay_when_paid_ok():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.ban_pay_when_paid")
    t = "Payments to subcontractors shall follow a fair payment schedule with statutory interest for late payment."
    out = run_rule(spec, AI(t, "payments"))
    assert not out or len(out.findings) == 0

# --- step-in / CRTPA alignment ---
def test_step_in_missing_crtpa():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.step_in_third_party_alignment")
    t = "Company may step-in or require novation of any subcontract."
    out = run_rule(spec, AI(t, "subcontracts"))
    assert out and any("CRTPA" in " ".join(f.legal_basis) or "collateral" in f.suggestion.text.lower() for f in out.findings)

def test_step_in_with_crtpa_or_collateral():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.step_in_third_party_alignment")
    t = "Company may step-in; CRTPA 1999 carve-out is included and collateral warranties from key subcontractors are required."
    out = run_rule(spec, AI(t, "subcontracts"))
    assert not out or len(out.findings) == 0

# --- copies & audit rights ---
def test_copies_and_audit_missing():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.copies_audit_rights")
    t = "Contractor may appoint subcontracts at its discretion."
    out = run_rule(spec, AI(t, "audit"))
    msgs = " ".join(f.message for f in out.findings)
    assert "copies of subcontracts" in msgs.lower() or "audit" in msgs.lower()

def test_copies_and_audit_present():
    spec = load_rule("core/rules/subcontracts/subcontracts_universal.yaml", rule_id="subcontracts.copies_audit_rights")
    t = "Provide copies of subcontracts within 10 days (limited redactions). Company retains audit and inspection rights."
    out = run_rule(spec, AI(t, "audit"))
    assert not out or len(out.findings) == 0
