import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput

def AI(text, clause="definitions", doc="Master Agreement"):
    return AnalysisInput(clause_type=clause, text=text,
                         metadata={"jurisdiction":"UK","doc_type":doc})

# 1) Site
def test_site_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/01_site_ownership_access_risk.yaml")
    t = "Site means any location."
    out = run_rule(spec, AI(t, clause="site"))
    assert out is not None and len(out.findings) >= 1

def test_site_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/01_site_ownership_access_risk.yaml")
    t = ("Site means locations owned, leased, licensed or under the control of the Company or its Affiliates; "
         "access rights (easements) and HSE permit-to-work apply; risk is aligned with Clause 19 and insurance with Clause 20; "
         "Worksites are listed in each Call-Off.")
    out = run_rule(spec, AI(t, clause="site"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 2) Specifications
def test_specs_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/02_specifications_versioning_variations.yaml")
    t = "Specifications means documents as updated from time to time."
    out = run_rule(spec, AI(t, clause="specifications"))
    assert out is not None and any("dynamic updates" in f.message.lower() or "dcc" in f.message.lower() for f in out.findings)

def test_specs_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/02_specifications_versioning_variations.yaml")
    t = ("Specifications are DCC-controlled (revision/date). Any update requires a Variation Order under Clause 14; "
         "the stricter of fitness-for-purpose or codes/standards prevails.")
    out = run_rule(spec, AI(t, clause="specifications"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 3) Subcontractor
def test_subcontractor_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/03_subcontractor_flowdown_audit.yaml")
    t = "Subcontractor means any direct subcontractor."
    out = run_rule(spec, AI(t, clause="subcontractor"))
    assert out is not None and len(out.findings) >= 1

def test_subcontractor_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/03_subcontractor_flowdown_audit.yaml")
    t = ("Subcontractor means any party at all tiers (tier-n), including suppliers of equipment and materials; "
         "flow-down includes HSE, anti-bribery/sanctions/export, IP/confidentiality and audit rights; critical subs require prior written approval.")
    out = run_rule(spec, AI(t, clause="subcontractor"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 4) Supplied Software
def test_supplied_software_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/04_supplied_software_scope_licence_escrow.yaml")
    t = "Supplied Software means software licensed for use."
    out = run_rule(spec, AI(t, clause="software"))
    assert out is not None and len(out.findings) >= 1

def test_supplied_software_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/04_supplied_software_scope_licence_escrow.yaml")
    t = ("Supplied Software includes executables, embedded components, utilities, keys/passwords/diagnostics, documentation and updates/patches; "
         "licence is worldwide, perpetual and royalty-free, allowing modify/integrate/test/DR/backup and sub-licence within the Company Group; "
         "clause 17 covers assignment in writing, waiver of moral rights and database right; critical software is subject to source code escrow.")
    out = run_rule(spec, AI(t, clause="software"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 5) Tariff Code
def test_tariff_code_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/05_tariff_code_classification.yaml")
    t = "Tariff Code means the code for customs."
    out = run_rule(spec, AI(t, clause="imports"))
    assert out is not None and len(out.findings) >= 1

def test_tariff_code_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/05_tariff_code_classification.yaml")
    t = "Commodity Code 8504403000 classified under HS 2022; classification evidence is available; duties and VAT implications are stated."
    out = run_rule(spec, AI(t, clause="imports"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 6) Taxes
def test_taxes_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/06_taxes_matrix_withholding_grossup.yaml")
    t = "Taxes means taxes."
    out = run_rule(spec, AI(t, clause="tax"))
    assert out is not None and len(out.findings) >= 1

def test_taxes_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/06_taxes_matrix_withholding_grossup.yaml")
    t = ("A responsibility matrix allocates Contractor Group taxes (payroll/NI/import/export duties/fees); "
         "withholding and gross-up mechanics apply with DTA relief; Taxes align with IoR/EoR and chosen Incoterms (e.g., DDP).")
    out = run_rule(spec, AI(t, clause="tax"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 7) Third Party
def test_third_party_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/07_third_party_crtpa_alignment.yaml")
    t = "Third Party means any person other than the parties."
    out = run_rule(spec, AI(t, clause="third party rights"))
    assert out is not None and len(out.findings) >= 1

def test_third_party_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/07_third_party_crtpa_alignment.yaml")
    t = "Third Party excludes the Company Group and the Contractor Group and aligns with the CRTPA carve-outs (Clause 32)."
    out = run_rule(spec, AI(t, clause="third party rights"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 8) Trade Tariff
def test_trade_tariff_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/08_trade_tariff_source_recency.yaml")
    t = "Trade Tariff means a tariff."
    out = run_rule(spec, AI(t, clause="imports"))
    assert out is not None and len(out.findings) >= 1

def test_trade_tariff_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/08_trade_tariff_source_recency.yaml")
    t = "Trade Tariff refers to the UK Trade Tariff (GOV.UK/CDS) and the HS/WCO basis; last checked date is recorded and applicable measures are listed."
    out = run_rule(spec, AI(t, clause="imports"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 9) TUPE
def test_tupe_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/09_tupe_eli_requirements.yaml")
    t = "TUPE applies."
    out = run_rule(spec, AI(t, clause="tupe"))
    assert out is not None and len(out.findings) >= 1

def test_tupe_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/09_tupe_eli_requirements.yaml")
    t = ("Transfer of Undertakings (Protection of Employment) Regulations 2006 (as amended); "
         "Employee Liability Information (Reg.11) snapshot and delivery deadlines apply with accuracy warranty and data protection safeguards.")
    out = run_rule(spec, AI(t, clause="tupe"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 10) Variation
def test_variation_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/10_variation_gate.yaml")
    t = "Variation means any change."
    out = run_rule(spec, AI(t, clause="variation"))
    assert out is not None and len(out.findings) >= 1

def test_variation_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/10_variation_gate.yaml")
    t = "Any change to Work/Price/Schedule only takes effect via a Variation Order under Clause 14; no proceeding without a signed VO."
    out = run_rule(spec, AI(t, clause="variation"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 11) VO
def test_vo_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/11_variation_order_contents.yaml")
    t = "Variation Order may be issued."
    out = run_rule(spec, AI(t, clause="variation"))
    assert out is not None and len(out.findings) >= 1

def test_vo_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/11_variation_order_contents.yaml")
    t = ("A Variation Order includes scope delta, Time Impact Analysis, price build-up, interfaces and effects on warranties/LDs, "
         "and references Clause 2.2 for order of precedence.")
    out = run_rule(spec, AI(t, clause="variation"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 12) VOR
def test_vor_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/12_variation_order_request_process.yaml")
    t = "A VOR may be sent."
    out = run_rule(spec, AI(t, clause="variation"))
    assert out is not None and len(out.findings) >= 1

def test_vor_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/12_variation_order_request_process.yaml")
    t = "A Variation Order Request may be initiated by either party; response/evaluation timelines apply (10 Business Days); proceeding without a signed VO is prohibited."
    out = run_rule(spec, AI(t, clause="variation"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 13) VAT
def test_vat_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/13_vat_registration_place_of_supply_zero_rating.yaml")
    t = "VAT means value added tax."
    out = run_rule(spec, AI(t, clause="vat"))
    assert out is not None and len(out.findings) >= 1

def test_vat_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/13_vat_registration_place_of_supply_zero_rating.yaml")
    t = ("VAT refers to the Value Added Tax Act 1994; Contractor provides VAT registration/number and valid tax invoices; "
         "place of supply/reverse charge rules may apply; evidence is required for zero-rating on export.")
    out = run_rule(spec, AI(t, clause="vat"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 14) Work
def test_work_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/14_work_scope_boundary_interfaces.yaml")
    t = "Work means all that is reasonably incidental."
    out = run_rule(spec, AI(t, clause="work"))
    assert out is not None and len(out.findings) >= 1

def test_work_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/14_work_scope_boundary_interfaces.yaml")
    t = ("Work includes explicit battery limits, interfaces and exclusions; QA/inspection regime applies and LDs may apply; "
         "changes to Work are only via VO.")
    out = run_rule(spec, AI(t, clause="work"))
    assert out is None or len(getattr(out, "findings", [])) == 0

# 15) Worksite
def test_worksite_negative():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/15_worksite_inclusion_exclusions.yaml")
    t = "Worksite means any place where work is done."
    out = run_rule(spec, AI(t, clause="worksite"))
    assert out is not None and len(out.findings) >= 1

def test_worksite_positive():
    spec = load_rule("core/rules/uk/definitions/s_to_w_block/15_worksite_inclusion_exclusions.yaml")
    t = ("Worksite includes locations of execution and excludes manufacturing/pre-delivery plants unless expressly listed; "
         "HSE/site rules apply and insurance applicability is stated.")
    out = run_rule(spec, AI(t, clause="worksite"))
    assert out is None or len(getattr(out, "findings", [])) == 0
