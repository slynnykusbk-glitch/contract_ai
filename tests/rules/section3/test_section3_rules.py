import pytest
from core.engine.runner import run_rule, load_rule
from core.schemas import AnalysisInput


def AI(text, clause="section3", doc="MSA"):
    return AnalysisInput(
        clause_type=clause, text=text, metadata={"jurisdiction": "UK", "doc_type": doc}
    )


# 01 battle of forms
def test_po_battle_forms_negative():
    spec = load_rule("core/rules/uk/section3/01_po_excludes_supplier_terms.yaml")
    t = "Supplier Terms apply; terms on the back of the PO shall apply."
    out = run_rule(spec, AI(t, clause="purchase order", doc="PO"))
    assert out is not None and len(out.findings) >= 1


def test_po_battle_forms_positive():
    spec = load_rule("core/rules/uk/section3/01_po_excludes_supplier_terms.yaml")
    t = "This Call-Off incorporates the MSA to the exclusion of all other terms; precedence per Clause 2.2.4."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 02 start-work acceptance
def test_start_work_acceptance_negative():
    spec = load_rule("core/rules/uk/section3/02_start_work_acceptance_guard.yaml")
    t = "Commencement of performance constitutes acceptance."
    out = run_rule(spec, AI(t, clause="formation"))
    assert out is not None and any("RTS risk" in f.message for f in out.findings)


def test_start_work_acceptance_positive():
    spec = load_rule("core/rules/uk/section3/02_start_work_acceptance_guard.yaml")
    t = "No work shall commence without a written Order specifying Price, SoW, LD, IP and HSE."
    out = run_rule(spec, AI(t, clause="formation"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 03 LD only remedy gates
def test_ld_only_remedy_negative():
    spec = load_rule("core/rules/uk/section3/03_ld_only_remedy_gate.yaml")
    t = "LD shall be the only remedy for delay."
    out = run_rule(spec, AI(t, clause="ld"))
    assert out is not None and len(out.findings) >= 1


def test_ld_only_remedy_positive():
    spec = load_rule("core/rules/uk/section3/03_ld_only_remedy_gate.yaml")
    t = "LD shall be the only remedy for delay, subject to Clause 3.10.3–3.10.5 and a maximum LD cap."
    out = run_rule(spec, AI(t, clause="ld"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 04 editorial blocker
def test_editorial_blocker_negative():
    spec = load_rule("core/rules/uk/section3/04_typo_numbering_blocker.yaml")
    t = "Notwithstanding C Company ... and the foregoing of this Clause 3.10.3 ... and partrial shipment ..."
    out = run_rule(spec, AI(t))
    assert out is not None and any("Editorial error" in f.message for f in out.findings)


def test_editorial_blocker_positive():
    spec = load_rule("core/rules/uk/section3/04_typo_numbering_blocker.yaml")
    t = "No editorial errors remain."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 05 no minimum commitment
def test_no_minimum_negative():
    spec = load_rule("core/rules/uk/section3/05_no_minimum_commitment.yaml")
    t = "Contractor shall purchase a minimum order of 1,000 hours per year."
    out = run_rule(spec, AI(t))
    assert out is not None and len(out.findings) >= 1


def test_no_minimum_positive():
    spec = load_rule("core/rules/uk/section3/05_no_minimum_commitment.yaml")
    t = "Nothing in this Agreement shall be construed as a guarantee of volume."
    out = run_rule(spec, AI(t))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 06 non exclusivity
def test_non_exclusive_negative():
    spec = load_rule("core/rules/uk/section3/06_non_exclusive.yaml")
    t = "Contractor shall be the exclusive supplier and has a right of first refusal."
    out = run_rule(spec, AI(t, clause="exclusivity"))
    assert out is not None and len(out.findings) >= 1


def test_non_exclusive_positive():
    spec = load_rule("core/rules/uk/section3/06_non_exclusive.yaml")
    t = "The relationship is non-exclusive."
    out = run_rule(spec, AI(t, clause="exclusivity"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 07 order channels align
def test_order_channels_negative():
    spec = load_rule("core/rules/uk/section3/07_order_channels_alignment.yaml")
    t = "Email shall not constitute writing. Supplier to send written acknowledgement."
    out = run_rule(spec, AI(t, clause="notices", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1


def test_order_channels_positive():
    spec = load_rule("core/rules/uk/section3/07_order_channels_alignment.yaml")
    t = "Written acknowledgement via DocuSign portal; Notices per Clause 29."
    out = run_rule(spec, AI(t, clause="notices", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 08 call-off contract execution
def test_contract_execution_negative():
    spec = load_rule("core/rules/uk/section3/08_calloff_contract_execution.yaml")
    t = "This Call-Off is subject to board approval."
    out = run_rule(spec, AI(t, clause="execution", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1


def test_contract_execution_positive():
    spec = load_rule("core/rules/uk/section3/08_calloff_contract_execution.yaml")
    t = "Executed by authorised signatories."
    out = run_rule(spec, AI(t, clause="execution", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 09 po per-entity responsibility
def test_po_per_entity_negative():
    spec = load_rule("core/rules/uk/section3/09_po_chain_per_entity.yaml")
    t = "Any Group entity shall be responsible and jointly and severally liable."
    out = run_rule(spec, AI(t, clause="purchase order", doc="PO"))
    assert out is not None and len(out.findings) >= 1


def test_po_per_entity_positive():
    spec = load_rule("core/rules/uk/section3/09_po_chain_per_entity.yaml")
    t = "Contractor looks only to the issuing Company under each PO."
    out = run_rule(spec, AI(t, clause="purchase order", doc="PO"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 10 order acceptance triggers
def test_order_acceptance_negative():
    spec = load_rule("core/rules/uk/section3/10_order_acceptance_triggers.yaml")
    t = "Acceptance by written confirmation."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1


def test_order_acceptance_positive():
    spec = load_rule("core/rules/uk/section3/10_order_acceptance_triggers.yaml")
    t = "Acceptance by written confirmation in accordance with Clause 29 or via e-signature portal."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 11 call-off minimum contents
def test_calloff_minimum_negative():
    spec = load_rule("core/rules/uk/section3/11_calloff_minimum_contents.yaml")
    t = "Call-Off for services."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1


def test_calloff_minimum_positive():
    spec = load_rule("core/rules/uk/section3/11_calloff_minimum_contents.yaml")
    t = "Call-Off: Company and Contractor; incorporates the MSA to the exclusion of all other terms; Scope; Price; Schedule with key dates."
    out = run_rule(spec, AI(t, clause="call-off", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 12 reliance vs entire/non-reliance
def test_reliance_negative():
    spec = load_rule("core/rules/uk/section3/12_reliance_vs_entire.yaml")
    t = "Company may rely on representations in the tender."
    out = run_rule(spec, AI(t, clause="reliance"))
    assert out is not None and len(out.findings) >= 1


def test_reliance_positive():
    spec = load_rule("core/rules/uk/section3/12_reliance_vs_entire.yaml")
    t = "Entire agreement with explicit non-reliance; agreed reliance carve-out where specified."
    out = run_rule(spec, AI(t, clause="reliance"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 13 NOM mods enforcement
def test_nom_negative():
    spec = load_rule("core/rules/uk/section3/13_nom_mods_enforcement.yaml")
    t = "The Supplier Terms apply and modify the Agreement."
    out = run_rule(spec, AI(t, clause="modification", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1


def test_nom_positive():
    spec = load_rule("core/rules/uk/section3/13_nom_mods_enforcement.yaml")
    t = "In the body of this Call-Off, we expressly modify Clause 3.10.4 as agreed; non-compliant changes are null and void under Clause 3.13."
    out = run_rule(spec, AI(t, clause="modification", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 14 LD parameters & cases
def test_ld_params_negative():
    spec = load_rule("core/rules/uk/section3/14_ld_parameters_and_cases.yaml")
    t = "Liquidated damages shall apply."
    out = run_rule(spec, AI(t, clause="ld"))
    assert out is not None and len(out.findings) >= 1


def test_ld_params_positive():
    spec = load_rule("core/rules/uk/section3/14_ld_parameters_and_cases.yaml")
    t = "LD: per day rate, cap as % of Contract Price, accrual until termination; LD apply notwithstanding partial possession."
    out = run_rule(spec, AI(t, clause="ld"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 15 unacceptable conditions 3.11
def test_unacceptable_conditions_negative():
    spec = load_rule("core/rules/uk/section3/15_unacceptable_conditions.yaml")
    t = "This Call-Off is subject to negotiation and supplier terms."
    out = run_rule(spec, AI(t, clause="acceptance", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1


def test_unacceptable_conditions_positive():
    spec = load_rule("core/rules/uk/section3/15_unacceptable_conditions.yaml")
    t = "No conditional signature; terms are final."
    out = run_rule(spec, AI(t, clause="acceptance", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 16 coventurers agent model
def test_coventurers_negative():
    spec = load_rule("core/rules/uk/section3/16_coventurers_agent_model.yaml")
    t = "Direct communications with Co-venturers are permitted."
    out = run_rule(spec, AI(t, clause="coventurers"))
    assert out is not None and len(out.findings) >= 1


def test_coventurers_positive():
    spec = load_rule("core/rules/uk/section3/16_coventurers_agent_model.yaml")
    t = "Company acts as agent for Co-venturers; communications pass via Company; aggregated cap applies."
    out = run_rule(spec, AI(t, clause="coventurers"))
    assert out is None or len(getattr(out, "findings", [])) == 0


# 17 foreign terms nullity 3.13
def test_foreign_terms_nullity_negative():
    spec = load_rule("core/rules/uk/section3/17_foreign_terms_nullity.yaml")
    t = "General Terms and Conditions of Sale shall apply."
    out = run_rule(spec, AI(t, clause="precedence", doc="Call-Off"))
    assert out is not None and len(out.findings) >= 1


def test_foreign_terms_nullity_positive():
    spec = load_rule("core/rules/uk/section3/17_foreign_terms_nullity.yaml")
    t = "Any conflicting Supplier Terms are null and void unless expressly modifying Clause X under 3.12."
    out = run_rule(spec, AI(t, clause="precedence", doc="Call-Off"))
    assert out is None or len(getattr(out, "findings", [])) == 0
