import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput


def AI(text, clause="representatives", doc="MSA"):
    return AnalysisInput(
        clause_type=clause, text=text, metadata={"jurisdiction": "UK", "doc_type": doc}
    )


# 01 CR appointment & guard
def test_cr_appointment_negative():
    spec = load_rule("core/rules/uk/section4/01_cr_appointment_and_scope.yaml")
    t = "Company Representative (CR) may issue instructions."
    out = run_rule(spec, AI(t))
    assert out is not None and any(
        "CR not expressly named" in f.message for f in out.findings
    )


def test_cr_appointment_positive():
    spec = load_rule("core/rules/uk/section4/01_cr_appointment_and_scope.yaml")
    t = (
        "Company Representative is named and appointed in writing."
        " Instruction does not constitute a Variation; changes to Scope/Price/Schedule require VO per Clause 14."
    )
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 02 CR NOM shield
def test_cr_nom_negative():
    spec = load_rule("core/rules/uk/section4/02_cr_nom_shield.yaml")
    t = "The CR may amend or waive terms agreed; oral modification via email minutes."
    out = run_rule(spec, AI(t, clause="modification"))
    assert out is not None and any(
        "NOM (3.12/3.13)" in f.message or "Off-channel" in f.message
        for f in out.findings
    )


def test_cr_nom_positive():
    spec = load_rule("core/rules/uk/section4/02_cr_nom_shield.yaml")
    t = "Modifications only via Clause 3.12; non-compliant changes are null and void under Clause 3.13."
    out = run_rule(spec, AI(t, clause="modification"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 03 Apparent authority controls
def test_apparent_authority_negative():
    spec = load_rule("core/rules/uk/section4/03_apparent_authority_controls.yaml")
    t = "Minutes of meeting: parties agreed to change schedule."
    out = run_rule(spec, AI(t, doc="Minutes"))
    assert out is not None and any(
        "Minutes lack disclaimer" in f.message or "No Instruction Register" in f.message
        for f in out.findings
    )


def test_apparent_authority_positive():
    spec = load_rule("core/rules/uk/section4/03_apparent_authority_controls.yaml")
    t = "Minutes are non-binding and do not constitute a Variation. Instruction Register maintained."
    out = run_rule(spec, AI(t, doc="Minutes"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 04 CTR appointment & limits
def test_ctr_appointment_negative():
    spec = load_rule("core/rules/uk/section4/04_ctr_appointment_and_limits.yaml")
    t = "CTR may modify terms."
    out = run_rule(spec, AI(t))
    assert out is not None and any(
        "CTR not expressly named" in f.message or "CTR purported to amend" in f.message
        for f in out.findings
    )


def test_ctr_appointment_positive():
    spec = load_rule("core/rules/uk/section4/04_ctr_appointment_and_limits.yaml")
    t = "Contractor Representative is named and appointed; CTR has no power to amend MSA."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 05 Delegation/ substitution
def test_delegation_negative():
    spec = load_rule("core/rules/uk/section4/05_delegation_and_substitution.yaml")
    t = "We delegate authority to John."
    out = run_rule(spec, AI(t, clause="delegation", doc="Notice"))
    assert out is not None and len(out.findings) >= 1


def test_delegation_positive():
    spec = load_rule("core/rules/uk/section4/05_delegation_and_substitution.yaml")
    t = "Delegation by notice stating scope of authority and effective from 01 Jan to 31 Mar. Delegation Register updated."
    out = run_rule(spec, AI(t, clause="delegation", doc="Notice"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 06 CTR change consent & SLA
def test_ctr_change_negative():
    spec = load_rule("core/rules/uk/section4/06_ctr_change_consent_sla.yaml")
    t = "Replace the Contractor Representative."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1


def test_ctr_change_positive():
    spec = load_rule("core/rules/uk/section4/06_ctr_change_consent_sla.yaml")
    t = "CTR change requires Company consent (not unreasonably withheld); deemed approved after 5 Business Days."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 07 Notice channels alignment
def test_notice_channels_negative():
    spec = load_rule("core/rules/uk/section4/07_notice_channels_alignment.yaml")
    t = "Email shall not constitute writing. CR will acknowledge in writing."
    out = run_rule(spec, AI(t, clause="notices"))
    assert out is not None and any(
        "no e-sign/portal path" in f.message or "Clause 29" in f.suggestion.text
        for f in out.findings
    )


def test_notice_channels_positive():
    spec = load_rule("core/rules/uk/section4/07_notice_channels_alignment.yaml")
    t = "Acknowledgement via DocuSign portal; Notices per Clause 29."
    out = run_rule(spec, AI(t, clause="notices"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 08 Instruction -> VO
def test_instruction_vo_negative():
    spec = load_rule("core/rules/uk/section4/08_instruction_triggers_vo.yaml")
    t = "CR instructs change that affects Price and Schedule."
    out = run_rule(spec, AI(t, clause="variations"))
    assert out is not None and any("no VO routing" in f.message for f in out.findings)


def test_instruction_vo_positive():
    spec = load_rule("core/rules/uk/section4/08_instruction_triggers_vo.yaml")
    t = "Any instruction impacting Scope/Price/Schedule/LD requires VOR/VO per Clause 14."
    out = run_rule(spec, AI(t, clause="variations"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 09 Stop Work Authority
def test_swa_negative():
    spec = load_rule("core/rules/uk/section4/09_stop_work_authority.yaml")
    t = "Safety rules apply."
    out = run_rule(spec, AI(t, clause="HSE", doc="HSE Policy"))
    assert out is not None and len(out.findings) >= 1


def test_swa_positive():
    spec = load_rule("core/rules/uk/section4/09_stop_work_authority.yaml")
    t = "Stop Work Authority is in place; no retaliation for exercising SWA."
    out = run_rule(spec, AI(t, clause="HSE", doc="HSE Policy"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 10 Chain of command clarity
def test_chain_of_command_negative():
    spec = load_rule("core/rules/uk/section4/10_chain_of_command_clarity.yaml")
    t = "Dual reporting lines may apply; conflicting instructions can be followed."
    out = run_rule(spec, AI(t))
    assert out is not None and any(
        "Conflicting directions" in f.message for f in out.findings
    )


def test_chain_of_command_positive():
    spec = load_rule("core/rules/uk/section4/10_chain_of_command_clarity.yaml")
    t = "Single chain of command via CR↔CTR; conflicts escalated to CR for resolution."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0
