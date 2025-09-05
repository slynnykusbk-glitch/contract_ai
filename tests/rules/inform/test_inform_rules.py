import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput

def AI(text, clause="inform", doc="Agreement"):
    return AnalysisInput(clause_type=clause, text=text,
                         metadata={"jurisdiction":"UK","doc_type":doc})

# 01 Deemed scope clarity
def test_deemed_scope_negative():
    spec = load_rule("core/rules/universal/inform/01_deemed_scope_clarity.yaml")
    t = "The Contractor is deemed to have informed itself."
    out = run_rule(spec, AI(t, clause="inform"))
    assert out and any("scope documents" in f.message for f in out.findings)

def test_deemed_scope_positive():
    spec = load_rule("core/rules/universal/inform/01_deemed_scope_clarity.yaml")
    t = "The Contractor is deemed to have informed itself of the Scope, Statement of Work and Specifications."
    out = run_rule(spec, AI(t, clause="inform"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 02 Deemed laws / Change in Law
def test_deemed_laws_negative():
    spec = load_rule("core/rules/universal/inform/02_deemed_laws_change.yaml")
    t = "The Contractor is deemed to be aware of all applicable laws."
    out = run_rule(spec, AI(t, clause="inform"))
    assert out and any("Change in Law" in f.suggestion.text for f in out.findings)

def test_deemed_laws_positive():
    spec = load_rule("core/rules/universal/inform/02_deemed_laws_change.yaml")
    t = "The Contractor is deemed aware of laws; Change in Law adjustments shall be made via Variation/time/price."
    out = run_rule(spec, AI(t, clause="inform"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 03 Deemed pricing / VO-EOT
def test_deemed_pricing_negative():
    spec = load_rule("core/rules/universal/inform/03_deemed_pricing_voeot.yaml")
    t = "Rates are sufficient with no adjustment or extension in any circumstances."
    out = run_rule(spec, AI(t, clause="pricing"))
    assert out and any("blocks all adjustment" in f.message for f in out.findings)

def test_deemed_pricing_positive():
    spec = load_rule("core/rules/universal/inform/03_deemed_pricing_voeot.yaml")
    t = "Rates are sufficient, save for bona fide Variations, Change in Law and Employer-caused delay (EOT)."
    out = run_rule(spec, AI(t, clause="pricing"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 04 Employer info / non-reliance
def test_employer_info_negative():
    spec = load_rule("core/rules/universal/inform/04_employer_info_nonreliance.yaml")
    t = "Information provided by Customer carries no warranty."
    out = run_rule(spec, AI(t, clause="information"))
    assert out and len(out.findings) >= 1

def test_employer_info_positive():
    spec = load_rule("core/rules/universal/inform/04_employer_info_nonreliance.yaml")
    t = ("Customer Provided Information: no warranty; parties agree basis/non-reliance; "
         "fraud/negligent misrepresentation expressly carved-out.")
    out = run_rule(spec, AI(t, clause="information"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 05 Discrepancy notice / time-bar
def test_discrepancy_notice_negative():
    spec = load_rule("core/rules/universal/inform/05_discrepancy_notice_timebar.yaml")
    t = "Contractor shall notify discrepancies promptly; claims may be time-barred."
    out = run_rule(spec, AI(t, clause="notice"))
    assert out and any("concrete notice window" in f.message or "mechanics are unclear" in f.message for f in out.findings)

def test_discrepancy_notice_positive():
    spec = load_rule("core/rules/universal/inform/05_discrepancy_notice_timebar.yaml")
    t = ("Notify discrepancies within 10 Business Days of discovery by written notice to the Contract Manager, "
         "stating issue/impact/evidence; failure results in time-bar.")
    out = run_rule(spec, AI(t, clause="notice"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 06 Employer corrects / Variation routing
def test_employer_corrects_negative():
    spec = load_rule("core/rules/universal/inform/06_employer_corrects_variation.yaml")
    t = "Errors may be addressed by the Contractor."
    out = run_rule(spec, AI(t, clause="discrepancies"))
    assert out and any("No obligation on Customer" in f.message or "No Variation/EOT routing" in f.message for f in out.findings)

def test_employer_corrects_positive():
    spec = load_rule("core/rules/universal/inform/06_employer_corrects_variation.yaml")
    t = "Customer shall correct its document errors and any impact shall be processed via Variation/EOT."
    out = run_rule(spec, AI(t, clause="discrepancies"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 07 Implied scope limit
def test_implied_scope_negative():
    spec = load_rule("core/rules/universal/inform/07_implied_scope_limit.yaml")
    t = "Contractor shall do all things necessary to perform the Works."
    out = run_rule(spec, AI(t, clause="scope"))
    assert out and any("Implied scope appears unlimited" in f.message for f in out.findings)

def test_implied_scope_positive():
    spec = load_rule("core/rules/universal/inform/07_implied_scope_limit.yaml")
    t = "Contractor shall perform incidental tasks necessary to perform; material additions require Variation."
    out = run_rule(spec, AI(t, clause="scope"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 08 Physical conditions unforeseen relief
def test_physical_conditions_negative():
    spec = load_rule("core/rules/universal/inform/08_physical_conditions_unforeseen.yaml")
    t = "Contractor bears all risk of physical conditions."
    out = run_rule(spec, AI(t, clause="site conditions"))
    assert out and any("unforeseen" in f.suggestion.text.lower() for f in out.findings)

def test_physical_conditions_positive():
    spec = load_rule("core/rules/universal/inform/08_physical_conditions_unforeseen.yaml")
    t = "Contractor bears risk of normal conditions; unforeseen/latent conditions give EOT and Variation."
    out = run_rule(spec, AI(t, clause="site conditions"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 09 Resources & breakdown carve-outs
def test_resources_breakdown_negative():
    spec = load_rule("core/rules/universal/inform/09_resources_breakdown_carveouts.yaml")
    t = "Contractor is responsible for all availability and all breakdowns."
    out = run_rule(spec, AI(t, clause="resources"))
    assert out and len(out.findings) >= 1

def test_resources_breakdown_positive():
    spec = load_rule("core/rules/universal/inform/09_resources_breakdown_carveouts.yaml")
    t = "Contractor responsible for availability/breakdowns, save for Employer interference/authority shutdowns (EOT applies)."
    out = run_rule(spec, AI(t, clause="resources"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 10 Transport of employer items
def test_transport_cpi_negative():
    spec = load_rule("core/rules/universal/inform/10_transport_employer_items.yaml")
    t = "Company Provided Items may be transported by Contractor."
    out = run_rule(spec, AI(t, clause="logistics"))
    assert out and any("risk transfer point" in f.message for f in out.findings)

def test_transport_cpi_positive():
    spec = load_rule("core/rules/universal/inform/10_transport_employer_items.yaml")
    t = "Risk passes at collection (DAP Named Place); aligns with Incoterms 2020."
    out = run_rule(spec, AI(t, clause="logistics"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 11 Notice mechanics
def test_notice_mechanics_negative():
    spec = load_rule("core/rules/universal/inform/11_notice_formalities.yaml")
    t = "A written notice must be given."
    out = run_rule(spec, AI(t, clause="notice"))
    assert out and len(out.findings) >= 1

def test_notice_mechanics_positive():
    spec = load_rule("core/rules/universal/inform/11_notice_formalities.yaml")
    t = "Notice by e-signed PDF or portal to Contract Manager (Attn.), stating issue/impact/evidence/requested instruction."
    out = run_rule(spec, AI(t, clause="notice"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 12 Stop-work safety/legal
def test_stop_work_negative():
    spec = load_rule("core/rules/universal/inform/12_stop_work_on_conflict.yaml")
    t = "Parties will comply with safety rules."
    out = run_rule(spec, AI(t, clause="HSE"))
    assert out and any("stop-work" in f.message or "suspend" in f.message.lower() for f in out.findings)

def test_stop_work_positive():
    spec = load_rule("core/rules/universal/inform/12_stop_work_on_conflict.yaml")
    t = "If safety/legal conflict arises, Contractor may stop-work until written instruction; no retaliation."
    out = run_rule(spec, AI(t, clause="HSE"))
    assert not out or len(getattr(out, "findings", [])) == 0
