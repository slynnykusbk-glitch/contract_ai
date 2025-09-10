import pytest
from core.engine.runner import load_rule, run_rule
from core.schemas import AnalysisInput

RULEPATH = "contract_review_app/legal_rules/policy_packs/title_core.yaml"

AI = lambda text: AnalysisInput(text=text, clause_type="title")


def run(rule_id, text):
    rule = load_rule(RULEPATH, rule_id=rule_id)
    return run_rule(rule, AI(text))

def test_t1_clean_title_pass():
    text = "Title to the Goods shall pass to Company free of any liens, charges, encumbrances or retention of title."
    res = run("title.clean.free_of_liens", text)
    assert res and any(f.message for f in res.findings)

def test_t2_vesting_warn_when_only_on_final_acceptance():
    text = "Title shall pass only upon final acceptance of the Goods by Company."
    res = run("title.vesting.early_wip_offsite", text)
    assert res and any("final acceptance" in f.message.lower() for f in res.findings)

def test_t3_marking_register_warn_when_missing_register():
    text = "Supplier shall mark materials as 'Property of Company' and keep them separate."
    res = run("title.marking.register.audit", text)
    assert res and any("no mention" in f.message.lower() for f in res.findings)

def test_t4_delivery_up_access_pass():
    text = ("Upon termination or insolvency, Company shall have the right to enter Supplier's premises and any warehouse "
            "to recover Company Property and require delivery-up of all off-site materials and WIP.")
    res = run("title.delivery_up.access_right", text)
    assert res and any("right to enter" in f.message.lower() for f in res.findings)

def test_t5_title_risk_warn_when_no_link():
    text = "Title to the Goods shall pass to Company upon delivery."
    res = run("title.risk.cross_reference", text)
    assert res and any("without" in f.message.lower() and "risk" in f.message.lower() for f in res.findings)

def test_t6_embedded_software_licence_pass():
    text = ("Embedded software shall be licensed to Company on a perpetual, royalty-free basis, sublicensable within the "
            "Company Group and shall survive termination. Activation keys, firmware and manuals shall be delivered.")
    res = run("title.embedded_software.perpetual_licence", text)
    assert res and any("perpetual" in f.message.lower() or "licence" in f.message.lower() for f in res.findings)

def test_t7_commingling_warn_missing_rules():
    text = "Supplier may commingle Company materials with others."
    res = run("title.commingling.bulk_processing", text)
    assert res and any("no rules" in f.message.lower() for f in res.findings)

def test_t8_rejection_return_warn_no_reversion():
    text = "Company may reject defective goods, and Supplier shall remove them."
    res = run("title.rejection.return_reversion", text)
    assert res and any("reversion" in f.message.lower() for f in res.findings)

def test_t9_waivers_fail_if_lien_allowed():
    text = "Any subcontractor or warehouseman may retain a lien over Company property."
    res = run("title.waivers.third_party_liens", text)
    assert res and any("lien rights" in f.message.lower() for f in res.findings)

def test_t10_customs_warn_on_absence():
    text = "Title to the Goods shall pass to Company on shipment."
    res = run("title.customs.ior_alignment", text)
    assert res and any("customs" in f.message.lower() for f in res.findings)
