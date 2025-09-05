import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput

def AI(text, clause="interpretation", doc="Master Agreement"):
    return AnalysisInput(clause_type=clause, text=text,
                         metadata={"jurisdiction":"UK","doc_type":doc})

# 01 xrefs
def test_xrefs_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/01_xrefs_links.yaml")
    t = "See Exhibit Z and Clause 99.9."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1

def test_xrefs_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/01_xrefs_links.yaml")
    t = "References to Recitals, Clauses and Exhibits listed in Clause 1.1 are updated per Clause 3.12."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 02 time basis
def test_time_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/02_time_periods_basis.yaml")
    t = "Notice must be served within 5 days."
    out = run_rule(spec, AI(t, clause="notices"))
    assert out is not None and len(out.findings) >= 1

def test_time_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/02_time_periods_basis.yaml")
    t = "Notice must be served within 5 Business Days (UK time) and aligned with Clause 29."
    out = run_rule(spec, AI(t, clause="notices"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 03 number/gender
def test_number_gender_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/03_number_gender.yaml")
    t = "Personnel means ... (narrow definition) ... singular includes plural."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1

def test_number_gender_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/03_number_gender.yaml")
    t = "Singular includes the plural and vice versa; specific definitions override where stated."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 04 including
def test_including_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/04_including_non_exhaustive.yaml")
    t = "Including A and B."
    out = run_rule(spec, AI(t, clause="specifications"))
    assert out is not None and len(out.findings) >= 1

def test_including_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/04_including_non_exhaustive.yaml")
    t = "Including, without limitation, A and B."
    out = run_rule(spec, AI(t, clause="specifications"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 05 company vs Company
def test_company_term_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/05_company_vs_Company.yaml")
    t = "The company agrees... The Company shall also..."
    out = run_rule(spec, AI(t, clause="parties"))
    assert out is not None and len(out.findings) >= 1

def test_company_term_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/05_company_vs_Company.yaml")
    t = "The Company (defined) agrees; references to a generic company are lower case only when not the defined Party."
    out = run_rule(spec, AI(t, clause="parties"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 06 person scope
def test_person_scope_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/06_person_scope.yaml")
    t = "Person includes individuals and companies."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1

def test_person_scope_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/06_person_scope.yaml")
    t = "Person includes individuals, companies, public authorities and associations; aligned with Governmental Authority and Third Party."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 07 dynamic incorporation
def test_dynamic_incorp_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/07_dynamic_incorp_variation.yaml")
    t = "Company Policies apply as updated from time to time."
    out = run_rule(spec, AI(t, clause="policies"))
    assert out is not None and len(out.findings) >= 1

def test_dynamic_incorp_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/07_dynamic_incorp_variation.yaml")
    t = "Company Policies apply as updated from time to time subject to Clause 14 Variation and cost/time adjustments."
    out = run_rule(spec, AI(t, clause="policies"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 08 approvals
def test_approvals_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/08_approvals_writing_reps.yaml")
    t = "Approval must be in writing; silence may be deemed approval."
    out = run_rule(spec, AI(t, clause="approvals"))
    assert out is not None and len(out.findings) >= 1

def test_approvals_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/08_approvals_writing_reps.yaml")
    t = "Approval must be in writing by authorised Representatives; silence is not approval."
    out = run_rule(spec, AI(t, clause="approvals"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 09 writing/email/e-sign
def test_writing_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/09_writing_email_esign.yaml")
    t = "Email shall not constitute writing."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1

def test_writing_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/09_writing_email_esign.yaml")
    t = "Email shall not constitute writing; VO/approvals via DocuSign or secure portal; Notices follow Clause 29."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 10 call-off incorporates MSA
def test_calloff_incorp_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/10_calloff_incorp_msa.yaml")
    t = "Call-Off for services."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1

def test_calloff_incorp_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/10_calloff_incorp_msa.yaml")
    t = "This Call-Off incorporates the MSA and states precedence per Clause 2.2.4."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 11 subcontracts
def test_subcontracts_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/11_subcontracts_flowdown.yaml")
    t = "Subcontracts means agreements with direct subcontractors."
    out = run_rule(spec, AI(t, clause="subcontracts"))
    assert out is not None and len(out.findings) >= 1

def test_subcontracts_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/11_subcontracts_flowdown.yaml")
    t = "Subcontracts includes services, materials, equipment and Contractor Group Equipment with mandatory flow-down and audit rights."
    out = run_rule(spec, AI(t, clause="subcontracts"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 12 headings no effect
def test_headings_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/12_headings_no_effect.yaml")
    t = "Headings are for convenience only and do not affect interpretation."
    out = run_rule(spec, AI(t))
    assert out is None

# 13 precedence Agreement alpha
def test_precedence_alpha_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/13_precedence_agreement_alpha.yaml")
    t = "Order of precedence: Exhibits in alphabetical order."
    out = run_rule(spec, AI(t, clause="precedence"))
    assert out is not None and len(out.findings) >= 1

def test_precedence_alpha_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/13_precedence_agreement_alpha.yaml")
    t = "Order of precedence: Clauses over Exhibits; purpose-based precedence applies."
    out = run_rule(spec, AI(t, clause="precedence"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 14 precedence Call-Off
def test_precedence_calloff_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/14_precedence_calloff.yaml")
    t = "Supplier Terms apply to this PO."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1

def test_precedence_calloff_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/14_precedence_calloff.yaml")
    t = "Any modification of the MSA must expressly modify Clause X under Clause 3.12; Supplier T&Cs are excluded; precedence follows 2.2.4."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 15 ambiguity → DR
def test_ambiguity_dr_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/15_ambiguity_dr_checks.yaml")
    t = "Escalate to Dispute Resolution."
    out = run_rule(spec, AI(t, clause="dispute resolution"))
    assert out is not None and len(out.findings) >= 1

def test_ambiguity_dr_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/15_ambiguity_dr_checks.yaml")
    t = "Before Dispute Resolution, the Parties will apply the mutually explanatory and stricter-of rules."
    out = run_rule(spec, AI(t, clause="dispute resolution"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 16 correlative
def test_correlative_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/16_correlative_scope_creep.yaml")
    t = "Documents are mutually explanatory."
    out = run_rule(spec, AI(t, clause="interpretation"))
    assert out is not None and len(out.findings) >= 1

def test_correlative_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/16_correlative_scope_creep.yaml")
    t = "Documents are mutually explanatory; boundaries (battery limits, interfaces, exclusions) apply; extras require a Variation Order."
    out = run_rule(spec, AI(t, clause="interpretation"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 17 stringency / fitness
def test_stringency_negative():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/17_stringency_fitness.yaml")
    t = "The stricter standard shall apply."
    out = run_rule(spec, AI(t, clause="specifications"))
    assert out is not None and len(out.findings) >= 1

def test_stringency_positive():
    spec = load_rule("core/rules/uk/interpretation/2_2_rules/17_stringency_fitness.yaml")
    t = "The stricter standard (including fitness-for-purpose) shall apply with cost/time adjustments via a Variation Order under Clause 14."
    out = run_rule(spec, AI(t, clause="specifications"))
    assert out is None or len(getattr(out, "findings", [])) == 0

