from core.engine.runner import load_rule, run_rule
from core.schemas import AnalysisInput


AI = lambda text, clause: AnalysisInput(text=text, clause_type=clause)


def _load(rule_id):
    # If storing YAML only in production path, change the path below accordingly
    return load_rule(
        "core/rules/independent_contractor/independent_contractor_universal.yaml",
        rule_id=rule_id,
    )


# --- Control over methods/hours ---
def test_control_methods_flag():
    spec = _load("ic.status.control.methods")
    t = (
        "The Company shall direct how, when, and where the services are performed with fixed"
        " hours as directed by the Company."
    )
    out = run_rule(spec, AI(t, "independent contractor"))
    assert out and any("control" in f.message.lower() for f in out.findings)


def test_outcome_only_ok():
    spec = _load("ic.status.control.methods")
    t = (
        "Supplier controls means and supervision; the Company sets outcome milestones and site"
        " safety rules only."
    )
    out = run_rule(spec, AI(t, "independent contractor"))
    assert not out or len(out.findings) == 0


# --- Substitution ---
def test_no_substitution_flag():
    spec = _load("ic.substitution.absent_or_personal_service")
    t = "Consultant shall provide the services personally and has no right to substitution."
    out = run_rule(spec, AI(t, "personnel"))
    assert out and any("personal service" in f.message.lower() for f in out.findings)


def test_genuine_substitution_ok():
    spec = _load("ic.substitution.absent_or_personal_service")
    t = (
        "Supplier may provide a qualified substitute subject to site/H&S vetting; Supplier remains"
        " liable; consent not unreasonably withheld."
    )
    out = run_rule(spec, AI(t, "personnel"))
    assert not out or len(out.findings) == 0


# --- MOO ---
def test_moo_flag():
    spec = _load("ic.mutuality.moo.minimum_hours")
    t = (
        "The Company shall provide work and the Contractor shall accept; minimum hours per week"
        " are guaranteed."
    )
    out = run_rule(spec, AI(t, "scheduling"))
    assert out and any("moo" in f.message.lower() for f in out.findings)


def test_task_based_ok():
    spec = _load("ic.mutuality.moo.minimum_hours")
    t = (
        "Services are provided on a task/call-off basis; no guarantee of continuous work or"
        " mandatory acceptance."
    )
    out = run_rule(spec, AI(t, "scheduling"))
    assert not out or len(out.findings) == 0


# --- Agency authority ---
def test_agency_flag():
    spec = _load("ic.agency.no_authority_to_bind")
    t = "Supplier may enter into contracts on behalf of the Company."
    out = run_rule(spec, AI(t, "authority"))
    assert out and any("agency" in f.message.lower() for f in out.findings)


def test_no_authority_ok():
    spec = _load("ic.agency.no_authority_to_bind")
    t = (
        "Supplier has no authority to bind the Company; any portal access is administrative only."
    )
    out = run_rule(spec, AI(t, "authority"))
    assert not out or len(out.findings) == 0


# --- Removal right ---
def test_removal_any_reason_flag():
    spec = _load("ic.removal.right.objective_non_discrimination")
    t = "The Company may remove any individual at any time for any reason."
    out = run_rule(spec, AI(t, "personnel"))
    assert out and any("removal" in f.message.lower() for f in out.findings)


def test_removal_objective_ok():
    spec = _load("ic.removal.right.objective_non_discrimination")
    t = (
        "The Company may require removal for H&S, competence, or misconduct; no discrimination;"
        " Supplier to replace promptly at no extra cost."
    )
    out = run_rule(spec, AI(t, "personnel"))
    assert not out or len(out.findings) == 0


# --- IR35 / SDS ---
def test_ir35_sds_missing_flag():
    spec = _load("ic.ir35.offpayroll.sds_process")
    t = "Off-payroll applies to PSC engagements."
    out = run_rule(spec, AI(t, "taxes"))
    assert out and any("sds" in f.message.lower() for f in out.findings)


def test_ir35_sds_present_ok():
    spec = _load("ic.ir35.offpayroll.sds_process")
    t = (
        "The Client will issue a Status Determination Statement with reasons using reasonable care"
        " and a challenge window; parties shall notify changes and allocate tax/NIC liabilities."
    )
    out = run_rule(spec, AI(t, "taxes"))
    assert not out or len(out.findings) == 0


# --- Vicarious liability wording ---
def test_vicarious_supervision_flag():
    spec = _load("ic.vicarious.liability.supervision_language")
    t = "The Company shall supervise and control Supplier personnel."
    out = run_rule(spec, AI(t, "management"))
    assert out and any("vicarious" in f.message.lower() for f in out.findings)


def test_vicarious_carveout_ok():
    spec = _load("ic.vicarious.liability.supervision_language")
    t = (
        "Supplier retains sole supervision and control; the Company sets safety rules and outcome"
        " criteria only."
    )
    out = run_rule(spec, AI(t, "management"))
    assert not out or len(out.findings) == 0


# --- HSE carve-out ---
def test_hse_carveout_missing_flag():
    spec = _load("ic.hse.carveout.required")
    t = "Supplier shall comply with health and safety and site rules."
    out = run_rule(spec, AI(t, "HSE"))
    assert out and any("carve" in f.message.lower() for f in out.findings)


def test_hse_carveout_present_ok():
    spec = _load("ic.hse.carveout.required")
    t = (
        "Supplier shall comply with site and H&S rules; such compliance does not create employment or"
        " method-control relationship."
    )
    out = run_rule(spec, AI(t, "HSE"))
    assert not out or len(out.findings) == 0


# --- AWR ---
def test_awr_missing_flag():
    spec = _load("ic.awr.agency_workers_equal_treatment")
    t = "The engagement is via an employment business and the individual is an agency worker."
    out = run_rule(spec, AI(t, "agency"))
    assert out and any("awr" in f.message.lower() for f in out.findings)


def test_awr_present_ok():
    spec = _load("ic.awr.agency_workers_equal_treatment")
    t = (
        "Agency worker provisions apply with equal treatment after 12 weeks in accordance with the"
        " Agency Workers Regulations 2010."
    )
    out = run_rule(spec, AI(t, "agency"))
    assert not out or len(out.findings) == 0


# --- Medical data minimisation ---
def test_medical_overbroad_flag():
    spec = _load("ic.medical.data.minimisation")
    t = "Supplier shall provide full medical records of all personnel."
    out = run_rule(spec, AI(t, "privacy"))
    assert out and any("medical" in f.message.lower() for f in out.findings)


def test_medical_minimised_ok():
    spec = _load("ic.medical.data.minimisation")
    t = (
        "Supplier shall provide fitness-to-work certificates and necessary screenings only; DPIA will"
        " be performed if large-scale."
    )
    out = run_rule(spec, AI(t, "privacy"))
    assert not out or len(out.findings) == 0

