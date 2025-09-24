import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput


def AI(text, clause="definitions", doc="Master Agreement"):
    return AnalysisInput(
        clause_type=clause, text=text, metadata={"jurisdiction": "UK", "doc_type": doc}
    )


# 1) IoR
def test_ior_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/01_importer_of_record.yaml"
    )
    t = "Importer of Record (IoR) means the responsible party."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is not None and any(
        "ior is defined" in f.message.lower() or "eori" in f.message.lower()
        for f in out.findings
    )


def test_ior_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/01_importer_of_record.yaml"
    )
    t = (
        "Each Call-Off shall specify the Importer of Record and its EORI (GB123456789000), "
        "declare the import jurisdiction, and confirm duties: customs declarations (SDE only if authorised) "
        "and records retention for at least 4 years."
    )
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 2) Indemnify
def test_indemnify_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/02_indemnify_controls.yaml"
    )
    t = "Contractor shall indemnify and hold harmless Company from all losses."
    out = run_rule(spec, AI(t, clause="indemnity"))
    assert out is not None and any(
        "defend" in f.message.lower() or "negligence" in f.message.lower()
        for f in out.findings
    )


def test_indemnify_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/02_indemnify_controls.yaml"
    )
    t = (
        "Contractor shall defend, indemnify and hold harmless; Contractor controls the defence subject to "
        "Company’s consent to any settlement; wording clarifies treatment of negligence."
    )
    out = run_rule(spec, AI(t, clause="indemnity"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 3) IP Rights
def test_ip_rights_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/03_ip_rights_coverage.yaml"
    )
    t = "IP Rights include patents, copyright and designs."
    out = run_rule(spec, AI(t))
    assert out is not None and any(
        "database right" in f.message.lower() or "assignment" in f.message.lower()
        for f in out.findings
    )


def test_ip_rights_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/03_ip_rights_coverage.yaml"
    )
    t = (
        "IP Rights include worldwide rights in patents, copyright, database right (1997), "
        "designs, trademarks, semiconductor topography and know-how; clause 17 requires assignment in writing and waiver of moral rights."
    )
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 4) Invitee
def test_invitee_negative():
    spec = load_rule("core/rules/uk/definitions/i_to_p_block/04_invitee_scope.yaml")
    t = "Invitee includes any Regulator visiting the Site."
    out = run_rule(spec, AI(t, clause="site"))
    assert out is not None and any(
        "regulators" in f.message.lower() for f in out.findings
    )


def test_invitee_positive():
    spec = load_rule("core/rules/uk/definitions/i_to_p_block/04_invitee_scope.yaml")
    t = "Governmental Authorities are not Invitees of either party; Invitee is a contract term distinct from OLA 1957."
    out = run_rule(spec, AI(t, clause="site"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 5) IP Rights Claim
def test_ip_claim_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/05_ip_rights_claim_mechanics.yaml"
    )
    t = "IP Rights Claim means any allegation of infringement."
    out = run_rule(spec, AI(t, clause="ip"))
    assert out is not None and any(
        "defence obligation" in f.message.lower() or "remedy suite" in f.message.lower()
        for f in out.findings
    )


def test_ip_claim_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/05_ip_rights_claim_mechanics.yaml"
    )
    t = "Upon an IP Rights Claim, Contractor shall defend; Company shall promptly notify within 10 days; remedies include replace, modify or procure a licence; carve-outs for combinations and Company modifications apply."
    out = run_rule(spec, AI(t, clause="ip"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 6) Key Personnel
def test_key_personnel_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/06_key_personnel_controls.yaml"
    )
    t = "Key Personnel are those designated by Contractor."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is not None and any(
        "scheduled" in f.message.lower()
        or "consent"
        in (f.suggestion.text.lower() if getattr(f, "suggestion", None) else "")
        for f in out.findings
    )


def test_key_personnel_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/06_key_personnel_controls.yaml"
    )
    t = "Key Personnel are listed in each Call-Off; no removal without Company’s prior written consent; LDs apply proportionately."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 7) Legal Fault
def test_legal_fault_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/07_legal_fault_consistency.yaml"
    )
    t = "Force Majeure may apply to any event beyond control."
    out = run_rule(spec, AI(t, clause="force majeure"))
    assert out is not None and any(
        "fm does not clearly exclude" in f.message.lower() for f in out.findings
    )


def test_legal_fault_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/07_legal_fault_consistency.yaml"
    )
    t = "Force Majeure shall not apply to events caused by the fault of the affected party; knock-for-knock indemnities clarify precedence."
    out = run_rule(spec, AI(t, clause="force majeure"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 8) Nonconformity
def test_nonconformity_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/08_nonconformity_vs_defect.yaml"
    )
    t = "Nonconformity means failure to meet specifications."
    out = run_rule(spec, AI(t, clause="quality"))
    assert out is not None and any(
        "relationship" in f.message.lower() or "priority" in f.message.lower()
        for f in out.findings
    )


def test_nonconformity_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/08_nonconformity_vs_defect.yaml"
    )
    t = "Nonconformity aligns with Defect; stricter of fitness-for-purpose or codes prevails."
    out = run_rule(spec, AI(t, clause="quality"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 9) Parties
def test_parties_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/09_parties_calloff_specificity.yaml"
    )
    t = "Call-Off may be issued by Company or its affiliates."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is not None and any(
        "naming" in f.message.lower() or "agency" in f.message.lower()
        for f in out.findings
    )


def test_parties_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/09_parties_calloff_specificity.yaml"
    )
    t = "Each Call-Off names the issuing Company entity and the Contractor entity; any agency is limited to the issuing entity and aligned with CRTPA carve-outs."
    out = run_rule(spec, AI(t, clause="call-off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 10) Permit
def test_permit_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/10_permit_authorisations_matrix.yaml"
    )
    t = "Permit means any approval."
    out = run_rule(spec, AI(t, clause="permit"))
    assert out is not None and any(
        "holder" in f.message.lower() or "authorisations" in f.message.lower()
        for f in out.findings
    )


def test_permit_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/10_permit_authorisations_matrix.yaml"
    )
    t = "Permit holder is Contractor; copies provided on request; permits link to the Authorisations responsibility matrix."
    out = run_rule(spec, AI(t, clause="permit"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 11) Personal Injury
def test_personal_injury_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/11_personal_injury_scope_and_insurance.yaml"
    )
    t = "Personal Injury means bodily injury."
    out = run_rule(spec, AI(t, clause="liability"))
    assert out is not None and any(
        "scope not broad" in f.message.lower() or "el insurance" in f.message.lower()
        for f in out.findings
    )


def test_personal_injury_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/11_personal_injury_scope_and_insurance.yaml"
    )
    t = "Personal Injury includes death, disease and mental distress; Employer’s Liability insurance evidence is maintained."
    out = run_rule(spec, AI(t, clause="liability"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 12) Personnel
def test_personnel_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/12_personnel_ir35_awr.yaml"
    )
    t = "Personnel means employees."
    out = run_rule(spec, AI(t, clause="personnel"))
    assert out is not None and any(
        "too narrow" in f.message.lower()
        or "ir35"
        in (f.suggestion.text.lower() if getattr(f, "suggestion", None) else "")
        for f in out.findings
    )


def test_personnel_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/12_personnel_ir35_awr.yaml"
    )
    t = "Personnel include employees, agency workers, consultants and seconded staff; Contractor bears PAYE/NI/visa; IR35/off-payroll and AWR 2010 (12 weeks) are addressed."
    out = run_rule(spec, AI(t, clause="personnel"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 13) Property
def test_property_negative():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/13_property_exclusions_title_risk.yaml"
    )
    t = "Property means any property of Company."
    out = run_rule(spec, AI(t, clause="property"))
    assert out is not None and any(
        "exclusions" in f.message.lower() for f in out.findings
    )


def test_property_positive():
    spec = load_rule(
        "core/rules/uk/definitions/i_to_p_block/13_property_exclusions_title_risk.yaml"
    )
    t = "Property excludes Company Provided Items, Goods before delivery/acceptance, and Agreement Documentation; cross-references Title, Risk and Insurance."
    out = run_rule(spec, AI(t, clause="property"))
    assert out is None or len(getattr(out, "findings", [])) == 0
