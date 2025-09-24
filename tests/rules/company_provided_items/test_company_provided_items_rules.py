from core.engine.runner import load_rule, run_rule
from core.schemas import AnalysisInput

AI = lambda text, clause: AnalysisInput(text=text, clause_type=clause)


def _load(rule_id):
    # укажите путь: зеркальный (core) или production; оставьте один вариант
    return load_rule(
        "core/rules/company_provided_items/company_provided_items_universal.yaml",
        rule_id=rule_id,
    )
    # return load_rule("contract_review_app/legal_rules/policy_packs/company_provided_items_universal.yaml", rule_id=rule_id)


# --- Exhaustive list ---
def test_cpi_open_ended_list_flag():
    spec = _load("cpi.register.exhaustive_list")
    t = "Company Provided Items include, without limitation, tools and fixtures."
    out = run_rule(spec, AI(t, "company provided items"))
    assert out and any("open-ended" in f.message.lower() for f in out.findings)


def test_cpi_fixed_schedule_ok():
    spec = _load("cpi.register.exhaustive_list")
    t = "Company Provided Items are listed exhaustively in Schedule CPI-1 (dated), with IDs and quantities."
    out = run_rule(spec, AI(t, "company provided items"))
    assert not out or len(out.findings) == 0


# --- 24h notice + latent ---
def test_cpi_24h_without_latent_flag():
    spec = _load("cpi.receipt.notice_window.latent")
    t = "Contractor shall notify defects within 24 hours of delivery."
    out = run_rule(spec, AI(t, "company provided items"))
    assert out and any(
        "latent" in f.message.lower()
        or (f.suggestion and "latent" in f.suggestion.text.lower())
        for f in out.findings
    )


def test_cpi_24h_with_latent_ok():
    spec = _load("cpi.receipt.notice_window.latent")
    t = "Notify defects within 24 hours; latent/hidden defects within a reasonable time after discovery."
    out = run_rule(spec, AI(t, "company provided items"))
    assert not out or len(out.findings) == 0


# --- Marking/tracking ---
def test_cpi_marking_missing_flag():
    spec = _load("cpi.marking.tracking.required")
    t = "Customer Property shall be returned on completion."
    out = run_rule(spec, AI(t, "customer property"))
    assert out and any("mark" in f.message.lower() for f in out.findings)


def test_cpi_marking_present_ok():
    spec = _load("cpi.marking.tracking.required")
    t = "Owner-furnished items shall be marked 'Property of Company', identified by asset IDs and tracked in ERP."
    out = run_rule(spec, AI(t, "owner-furnished"))
    assert not out or len(out.findings) == 0


# --- LOLER/PUWER ---
def test_cpi_lifting_no_loler_flag():
    spec = _load("cpi.storage.lifting.loler_puwer")
    t = "Use crane and slings to handle CPI."
    out = run_rule(spec, AI(t, "HSE"))
    assert out and any(
        "loler" in f.message.lower()
        or (f.suggestion and "loler" in f.suggestion.text.lower())
        for f in out.findings
    )


def test_cpi_lifting_with_loler_ok():
    spec = _load("cpi.storage.lifting.loler_puwer")
    t = "Lifting operations with CPI shall comply with LOLER/PUWER and be recorded."
    out = run_rule(spec, AI(t, "HSE"))
    assert not out or len(out.findings) == 0


# --- CCC insurance ---
def test_cpi_ccc_cover_missing_flag():
    spec = _load("cpi.ccc.insurance.cover_required")
    t = "Risk in CPI lies with Contractor while in its care, custody and control."
    out = run_rule(spec, AI(t, "insurance"))
    assert out and any(
        "ccc" in f.message.lower()
        or (f.suggestion and "ccc" in f.suggestion.text.lower())
        for f in out.findings
    )


def test_cpi_ccc_cover_present_ok():
    spec = _load("cpi.ccc.insurance.cover_required")
    t = "Contractor shall maintain CCC/bailee or CAR cover at replacement value and name Company as additional insured and loss payee."
    out = run_rule(spec, AI(t, "insurance"))
    assert not out or len(out.findings) == 0


# --- No lien ---
def test_cpi_lien_flag():
    spec = _load("cpi.no_lien.required")
    t = "Contractor may assert a lien over the equipment."
    out = run_rule(spec, AI(t, "liens"))
    assert out and any("lien" in f.message.lower() for f in out.findings)


def test_cpi_no_lien_ok():
    spec = _load("cpi.no_lien.required")
    t = "No lien or encumbrance shall arise over CPI/site/work; lien waivers required from Contractor and Subcontractors."
    out = run_rule(spec, AI(t, "liens"))
    assert not out or len(out.findings) == 0


# --- Waste duty of care ---
def test_cpi_waste_docs_flag():
    spec = _load("cpi.waste.disposal.duty_of_care")
    t = "Scrap CPI shall be disposed of by the Contractor."
    out = run_rule(spec, AI(t, "waste"))
    assert out and any("waste transfer" in f.message.lower() for f in out.findings)


def test_cpi_waste_docs_ok():
    spec = _load("cpi.waste.disposal.duty_of_care")
    t = "Dispose via licensed carriers; maintain waste transfer notes; provide certificates of destruction."
    out = run_rule(spec, AI(t, "waste"))
    assert not out or len(out.findings) == 0


# --- Sole-use restriction ---
def test_cpi_use_only_flag():
    spec = _load("cpi.use.only.for.project")
    t = "Company Provided Items are available for use."
    out = run_rule(spec, AI(t, "company provided items"))
    assert out and any("use" in f.message.lower() for f in out.findings)


def test_cpi_use_only_ok():
    spec = _load("cpi.use.only.for.project")
    t = "CPI shall be used solely for the Work and not for any other customer without prior written consent."
    out = run_rule(spec, AI(t, "company provided items"))
    assert not out or len(out.findings) == 0


# --- Incident reporting ---
def test_cpi_incident_window_flag():
    spec = _load("cpi.incident.loss.damage.reporting")
    t = "Any damage to Customer Property shall be recorded."
    out = run_rule(spec, AI(t, "incidents"))
    assert out and any(
        (f.suggestion and "report" in f.suggestion.text.lower()) for f in out.findings
    )


def test_cpi_incident_window_ok():
    spec = _load("cpi.incident.loss.damage.reporting")
    t = "Report loss or damage to CPI within 24 hours with evidence and insurer notice."
    out = run_rule(spec, AI(t, "incidents"))
    assert not out or len(out.findings) == 0


# --- Export/sanctions controls ---
def test_cpi_export_controls_flag():
    spec = _load("cpi.export.controls.sanctions")
    t = "Export Customer Property across the border."
    out = run_rule(spec, AI(t, "export"))
    assert out and any("export" in f.message.lower() for f in out.findings)


def test_cpi_export_controls_ok():
    spec = _load("cpi.export.controls.sanctions")
    t = "For cross-border CPI moves, define Importer/Exporter of Record, HS classification, licences and sanctions screening."
    out = run_rule(spec, AI(t, "export"))
    assert not out or len(out.findings) == 0
