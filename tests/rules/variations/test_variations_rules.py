import pytest
from contract_review_app.legal_rules import loader


def _find(rule_id: str, text: str):
    loader.load_rule_packs()
    for f in loader.match_text(text):
        if f["rule_id"] == rule_id:
            return [f]
    return []


def test_nom_only():
    text = "None of the scope, pricing, or time schedule provisions of a Call-Off is to be modified otherwise than in accordance with Clause 14 or Clause 31.6."
    fs = _find("VARIATIONS.NOM_ONLY", text)
    assert len(fs) == 1
    f = fs[0]
    assert f.get("advice")
    assert f.get("law_refs")
    assert f["severity"] == "high"
    assert f.get("occurrences", 0) >= 1


def test_vor_5bd_cpa_rateparity():
    text = (
        "Contractor shall provide the duly completed Variation Order Request as soon as reasonably practicable and notify if unable to provide all requested information within five (5) business days; pricing shall use the same rates or demonstrably commensurate rates and time impact shall be supported by proper critical path analysis."
    )
    vor = _find("VARIATIONS.VOR_5BD", text)
    rate = _find("VARIATIONS.RATE_PARITY_CPA", text)
    assert vor and rate
    for f in vor + rate:
        assert f.get("advice")
        assert f.get("law_refs")
        assert f.get("occurrences", 0) >= 1


def test_disagree_proceed_and_no_conditional_sign():
    text = (
        "If Contractor disagrees with a Variation Order, Company may instruct Contractor to proceed immediately; Contractor shall not sign contingent upon changes."
    )
    fs = _find("VARIATIONS.DISAGREE_PROCEED_NO_COND_SIGN", text)
    assert len(fs) == 1
    f = fs[0]
    assert f.get("advice")
    assert f.get("law_refs")
    assert f.get("occurrences", 0) >= 1


def test_timebar_offshore_and_3days():
    text = (
        "Contractor shall issue its request for a Variation Order immediately where the event relates to Work offshore, and in any other case as soon as possible and in any event not later than (3) days; failure to request within that period results in no entitlement."
    )
    fs = _find("VARIATIONS.TIMEBAR_IMMEDIATE_OFFSHORE_3D", text)
    assert len(fs) == 1
    f = fs[0]
    assert f["severity"] == "critical"
    assert f.get("advice")
    assert f.get("law_refs")
    assert f.get("occurrences", 0) >= 1


def test_change_in_law_excludes_taxes():
    text = (
        "Any Change in Law affecting Taxes or business in general does not entitle a Party to a Variation Order; strict enforcement of previously unenforced law does not constitute a Change in Law."
    )
    fs = _find("VARIATIONS.CHANGE_IN_LAW_TAXES_BUSINESS_EXCLUDED", text)
    assert len(fs) == 1
    f = fs[0]
    assert f.get("advice")
    assert f.get("law_refs")
    assert f.get("occurrences", 0) >= 1


def test_waiver_cumulative_cardinal():
    text = "Any Variation Order waives cardinal change and cumulative impact claims."
    fs = _find("VARIATIONS.WAIVER_CUMULATIVE_CARDINAL", text)
    assert len(fs) == 1
    f = fs[0]
    assert f.get("advice")
    assert f.get("law_refs")
    assert f.get("occurrences", 0) >= 1


def test_mitigation_mandatory():
    text = "No increase in the Contract Price shall be allowed if the Contractor failed to mitigate the impact."
    fs = _find("VARIATIONS.MITIGATION_DUTY", text)
    assert len(fs) == 1
    f = fs[0]
    assert f.get("advice")
    assert f.get("law_refs")
    assert f.get("occurrences", 0) >= 1


def test_negative_cases():
    text = "Variations may be agreed by the parties in writing."
    loader.load_rule_packs()
    ids = {f["rule_id"] for f in loader.match_text(text)}
    assert not any(rid.startswith("VARIATIONS.") for rid in ids)
