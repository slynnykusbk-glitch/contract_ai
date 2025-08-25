import pytest

from contract_review_app.engine import pipeline

SAMPLES = {
    "confidentiality_survival_term_min_3y": "Confidentiality survives termination.",
    "notices_formal_service": "Notices shall be sent to the addresses.",
    "assignment_consent_exceptions": "Assignment requires consent.",
    "subcontracting_control_flowdown": "Supplier may use subcontractors.",
    "ip_ownership_licenseback": "IP belongs to the customer.",
    "force_majeure_exclusions": "Force majeure applies.",
    "warranties_goods_services": "Supplier warrants goods.",
    "ip_infringement_indemnity": "Supplier defends IP claims.",
    "limitation_of_liability_cap_and_carveouts": "Liability is limited.",
    "data_protection_link_exhibit_M": "See Exhibit M.",
    "info_security_link_exhibit_L": "See Exhibit L.",
    "termination_for_convenience_no_anticipatory_profit": "Either party may terminate for convenience.",
}


@pytest.mark.parametrize("clause_type,text", SAMPLES.items())
def test_suggest_templates_provide_edits(clause_type, text):
    edits = pipeline.suggest_edits(text, clause_id=None, mode="friendly", clause_type=clause_type)
    assert edits, f"No edits returned for {clause_type}"
    edit = edits[0]
    assert isinstance(edit.get("proposed_text"), str)
    rng = edit.get("range", {})
    if edit.get("action") == "replace":
        assert rng.get("length", 0) > 0
    else:
        assert rng.get("start", -1) == len(text)
        assert rng.get("length", 1) == 0
