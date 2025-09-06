import pytest
from contract_review_app.legal_rules import loader

POS_SAMPLES = {
    "quality.qms.iso_required": "Contractor shall maintain a quality management system acceptable to Company.",
    "quality.itp.hw_notice_5d": "Contractor shall produce an inspection and test plan. The plan will list inspections only. No advance notice stated.",
    "quality.no_ship_without_final_inspection": "Contractor may ship the Goods without final inspection.",
    "quality.company.rights.reject_nonconforming": "Company may inspect the Goods in a reasonable time.",
}

NEGATIVE_TEXT = (
    "Contractor shall maintain a quality management system conforming to ISO 9001 or API Spec Q1 or Q2. "
    "Quality plans shall be developed in accordance with ISO 10005 and the first invoice is not payable until Company acceptance. "
    "Internal audits shall follow ISO 19011 and Company may participate. "
    "Contractor shall issue an inspection and test plan with Hold, Witness and Monitor points and notify Company five days prior. "
    "Company may reject nonconforming work and is not liable to pay for it. Contractor shall not ship any Goods without Company's final inspection or a written waiver."
)


def _find(rule_id: str, text: str):
    loader.load_rule_packs()
    findings = loader.match_text(text)
    for f in findings:
        if f["rule_id"] == rule_id:
            return f
    return None


@pytest.mark.parametrize("rule_id,text", POS_SAMPLES.items())
def test_rule_detects(rule_id: str, text: str):
    f = _find(rule_id, text)
    assert f is not None, f"{rule_id} not triggered"
    assert f.get("advice")
    assert isinstance(f.get("law_refs"), list) and f["law_refs"]


def test_negative_no_detection():
    loader.load_rule_packs()
    ids = {f["rule_id"] for f in loader.match_text(NEGATIVE_TEXT)}
    for rid in POS_SAMPLES.keys():
        assert rid not in ids
