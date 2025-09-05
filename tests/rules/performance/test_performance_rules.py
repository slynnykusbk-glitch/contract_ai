import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput

def AI(text, clause="performance", doc="Agreement"):
    return AnalysisInput(clause_type=clause, text=text,
                         metadata={"jurisdiction":"UK","doc_type":doc})

# 01 RSC vs FfP
def test_rsc_ffp_negative():
    spec = load_rule("core/rules/universal/performance/01_standard_rsc_vs_ffp.yaml")
    t = "Services shall be provided."
    out = run_rule(spec, AI(t))
    assert out and any("No explicit standard" in f.message or "priority" in getattr(f, "message","") for f in out.findings)

def test_rsc_ffp_positive():
    spec = load_rule("core/rules/universal/performance/01_standard_rsc_vs_ffp.yaml")
    t = ("Contractor shall exercise reasonable skill and care. "
         "If conflict, stricter fitness/output KPIs shall prevail.")
    out = run_rule(spec, AI(t))
    assert not out or len(getattr(out, "findings", [])) == 0

# 02 Resources
def test_resources_negative():
    spec = load_rule("core/rules/universal/performance/02_resources_sufficiency.yaml")
    t = "Contractor will perform work."
    out = run_rule(spec, AI(t, clause="resources"))
    assert out and any("resources" in f.message.lower() for f in out.findings)

def test_resources_positive():
    spec = load_rule("core/rules/universal/performance/02_resources_sufficiency.yaml")
    t = "Contractor shall provide all necessary resources (personnel, equipment, materials) at its cost."
    out = run_rule(spec, AI(t, clause="resources"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 03 Cooperate & EOT
def test_cooperate_eot_negative():
    spec = load_rule("core/rules/universal/performance/03_cooperate_eot.yaml")
    t = "There may be delay caused by others."
    out = run_rule(spec, AI(t, clause="schedule"))
    assert out and any("cooperate" in f.message.lower() or "Extension of Time" in f.message for f in out.findings)

def test_cooperate_eot_positive():
    spec = load_rule("core/rules/universal/performance/03_cooperate_eot.yaml")
    t = "Contractor shall cooperate and coordinate; delays by employer/others give Extension of Time."
    out = run_rule(spec, AI(t, clause="schedule"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 04 Permits/RTW
def test_permits_rtw_negative():
    spec = load_rule("core/rules/universal/performance/04_permits_rtw.yaml")
    t = "All personnel will be engaged."
    out = run_rule(spec, AI(t, clause="permits"))
    assert out and len(out.findings) >= 1

def test_permits_rtw_positive():
    spec = load_rule("core/rules/universal/performance/04_permits_rtw.yaml")
    t = "Permit responsibility matrix defines who/what/by when; right-to-work checks required before site access."
    out = run_rule(spec, AI(t, clause="permits"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 05 Document control / handover
def test_doc_control_negative():
    spec = load_rule("core/rules/universal/performance/05_document_control_handover.yaml")
    t = "Documents will be provided."
    out = run_rule(spec, AI(t, clause="document control"))
    assert out and any("latest" in f.message.lower() or "handover" in f.message.lower() for f in out.findings)

def test_doc_control_positive():
    spec = load_rule("core/rules/universal/performance/05_document_control_handover.yaml")
    t = "Work only on latest approved revision; completion subject to delivery of full handover pack."
    out = run_rule(spec, AI(t, clause="document control"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 06 Materials / CPI
def test_materials_negative():
    spec = load_rule("core/rules/universal/performance/06_materials_management.yaml")
    t = "We will store materials."
    out = run_rule(spec, AI(t, clause="materials"))
    assert out and len(out.findings) >= 1

def test_materials_positive():
    spec = load_rule("core/rules/universal/performance/06_materials_management.yaml")
    t = "Materials Management Procedure (WMS) in place incl. quarantine; Company Provided Items in contractor custody with risk allocation."
    out = run_rule(spec, AI(t, clause="materials"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 07 Reporting / Early warning
def test_reporting_negative():
    spec = load_rule("core/rules/universal/performance/07_reporting_early_warning.yaml")
    t = "Reports will be provided as needed."
    out = run_rule(spec, AI(t, clause="reporting"))
    assert out and len(out.findings) >= 1

def test_reporting_positive():
    spec = load_rule("core/rules/universal/performance/07_reporting_early_warning.yaml")
    t = "Weekly progress reports; early-warning obligation; shared risk register."
    out = run_rule(spec, AI(t, clause="reporting"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 08 Schedule / Recovery
def test_schedule_negative():
    spec = load_rule("core/rules/universal/performance/08_schedule_recovery.yaml")
    t = "Contractor will try to meet dates; there may be slippage."
    out = run_rule(spec, AI(t, clause="schedule"))
    assert out and any("key dates" in f.message.lower() or "recovery" in f.message.lower() for f in out.findings)

def test_schedule_positive():
    spec = load_rule("core/rules/universal/performance/08_schedule_recovery.yaml")
    t = "Key dates/milestones defined; on delay contractor submits recovery plan within 5 Business Days."
    out = run_rule(spec, AI(t, clause="schedule"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 09 Site / PTW / Partial occupation
def test_site_negative():
    spec = load_rule("core/rules/universal/performance/09_site_ptw_partial_occupation.yaml")
    t = "We will access the site; client may take partial possession."
    out = run_rule(spec, AI(t, clause="site"))
    assert out and len(out.findings) >= 1

def test_site_positive():
    spec = load_rule("core/rules/universal/performance/09_site_ptw_partial_occupation.yaml")
    t = "Permit-to-Work applies; partial occupation shall not constitute acceptance."
    out = run_rule(spec, AI(t, clause="site"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 10 Working hours & overtime
def test_overtime_negative():
    spec = load_rule("core/rules/universal/performance/10_working_hours_overtime.yaml")
    t = "Overtime may be worked."
    out = run_rule(spec, AI(t, clause="working hours"))
    assert out and len(out.findings) >= 1

def test_overtime_positive():
    spec = load_rule("core/rules/universal/performance/10_working_hours_overtime.yaml")
    t = "Overtime requires prior written approval; costs borne by the contractor when due to contractor delay."
    out = run_rule(spec, AI(t, clause="working hours"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 11 Goods/software/Incoterms
def test_goods_negative():
    spec = load_rule("core/rules/universal/performance/11_goods_software_incoterms.yaml")
    t = "Goods include embedded software."
    out = run_rule(spec, AI(t, clause="goods"))
    assert out and any("keys" in f.message.lower() or "incoterm" in f.message.lower() for f in out.findings)

def test_goods_positive():
    spec = load_rule("core/rules/universal/performance/11_goods_software_incoterms.yaml")
    t = "Deliver keys/passwords/licences and packing list; Incoterm 2020 DAP Named Place London DC, UK."
    out = run_rule(spec, AI(t, clause="goods"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 12 Inspection/acceptance window
def test_acceptance_negative():
    spec = load_rule("core/rules/universal/performance/12_inspection_acceptance_window.yaml")
    t = "Buyer may inspect."
    out = run_rule(spec, AI(t, clause="acceptance"))
    assert out and len(out.findings) >= 1

def test_acceptance_positive():
    spec = load_rule("core/rules/universal/performance/12_inspection_acceptance_window.yaml")
    t = "Inspection window of 10 Business Days from delivery; buyer may reject non-conforming items for repair/replace."
    out = run_rule(spec, AI(t, clause="acceptance"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 13 Rental equipment
def test_rental_negative():
    spec = load_rule("core/rules/universal/performance/13_rental_equipment.yaml")
    t = "Rented equipment will be provided."
    out = run_rule(spec, AI(t, clause="rental"))
    assert out and len(out.findings) >= 1

def test_rental_positive():
    spec = load_rule("core/rules/universal/performance/13_rental_equipment.yaml")
    t = "Provide manuals and maintenance instructions; risk of loss and insurance allocation defined."
    out = run_rule(spec, AI(t, clause="rental"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 14 Instructions / Variation gate
def test_instructions_negative():
    spec = load_rule("core/rules/universal/performance/14_instructions_variation_gate.yaml")
    t = "Customer may direct methods; impacts schedule."
    out = run_rule(spec, AI(t, clause="instructions"))
    assert out and len(out.findings) >= 1

def test_instructions_positive():
    spec = load_rule("core/rules/universal/performance/14_instructions_variation_gate.yaml")
    t = "Customer instructions focus on result; any impact to Scope/Price/Schedule requires a formal Change/Variation Order."
    out = run_rule(spec, AI(t, clause="instructions"))
    assert not out or len(getattr(out, "findings", [])) == 0

# 15 Exhibits/policies precedence
def test_policies_negative():
    spec = load_rule("core/rules/universal/performance/15_exhibits_policies_conflicts.yaml")
    t = "Policies may apply."
    out = run_rule(spec, AI(t, clause="policies"))
    assert out and len(out.findings) >= 1

def test_policies_positive():
    spec = load_rule("core/rules/universal/performance/15_exhibits_policies_conflicts.yaml")
    t = "Applicable policies/exhibits include A/B/C; order of precedence: Conditions > Scope/Specs > Standards/Policies > Forms."
    out = run_rule(spec, AI(t, clause="policies"))
    assert not out or len(getattr(out, "findings", [])) == 0
