from __future__ import annotations

from contract_review_app.legal_rules.aggregate import apply_merge_policy


ALLOWED_FINDING_KEYS = {
    "rule_id",
    "channel",
    "salience",
    "message",
    "anchor",
    "meta",
}


def test_analyze_api_contract_stable():
    findings = [
        {
            "rule_id": "presence-rule",
            "channel": "presence",
            "salience": 95,
            "message": "Presence rule fired",
            "anchor": {"start": 0, "end": 10},
        },
        {
            "rule_id": "policy-rule",
            "channel": "policy",
            "salience": 65,
            "message": "Policy guidance",
            "anchor": {"start": 40, "end": 55},
            "meta": {"entity_id": "policy"},
        },
    ]

    merged = apply_merge_policy(findings)
    assert len(merged) == 2
    for finding in merged:
        assert set(finding.keys()) <= ALLOWED_FINDING_KEYS
        assert "agenda_group" not in finding
