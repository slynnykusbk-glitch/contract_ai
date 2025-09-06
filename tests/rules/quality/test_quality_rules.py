import pytest
from contract_review_app.legal_rules import loader

SAMPLES_POS = {
    "13.QMS.ISO9001": "Supplier shall maintain a quality management system.",
    "13.QP.REQUIRED": "A quality plan shall be submitted and approved before the first invoice.",
    "13.AUDIT.ISO19011": "Internal audits shall be conducted in accordance with ISO 19011 and CAPA closed.",
    "13.MOC.FORMAL": "Changes to resources or suppliers shall follow a formal Management of Change process.",
    "13.ITP.EXISTS": "Contractor shall submit an Inspection & Test Plan (ITP) with Hold and Witness points.",
    "13.ITP.NOTICE": "Contractor shall give five days notice for any Hold or Witness point.",
    "13.COST.NOSHOW_FAIL": "Costs of re-test due to contractor no-show shall be borne by the contractor.",
    "13.INSPECT.NO_WAIVER": "Inspection does not waive liability and defective work will not be paid.",
    "13.HIDDEN.WORKS": "Hidden works not inspected shall be opened for evidence at contractor cost.",
    "13.SHIP.BLOCK": "No shipment without Company final inspection or a written waiver.",
    "13.EQUIP.CERT.LOLER_PUWER": "All lifting equipment shall have current certificates and SWL marked; expired certificate.",
    "13.LAB.ISO17025": "External testing shall be performed only by ISO/IEC 17025 accredited laboratories.",
    "13.MARKING.UKCA_CE": "Equipment shall bear the applicable UKCA or CE mark in accordance with PED 2016.",
}

NEUTRAL_TEXT = "The parties shall cooperate to deliver the project."


def _find(rule_id: str, text: str):
    loader.load_rule_packs()
    findings = loader.match_text(text)
    for f in findings:
        if f["rule_id"] == rule_id:
            return f
    return None


@pytest.mark.parametrize("rule_id,text", SAMPLES_POS.items())
def test_rule_detects(rule_id: str, text: str):
    f = _find(rule_id, text)
    assert f is not None, f"{rule_id} not triggered"
    assert f.get("advice")
    assert isinstance(f.get("law_refs"), list) and f["law_refs"]


def test_neutral_no_detection():
    loader.load_rule_packs()
    ids = {f["rule_id"] for f in loader.match_text(NEUTRAL_TEXT)}
    for rid in SAMPLES_POS.keys():
        assert rid not in ids
