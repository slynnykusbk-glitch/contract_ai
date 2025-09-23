from __future__ import annotations

from contract_review_app.legal_rules.aggregate import apply_merge_policy


def test_panel_order_visible():
    findings = [
        {
            "rule_id": "payment-timing",
            "channel": "substantive",
            "salience": 75,
            "anchor": {"start": 120, "end": 180},
            "meta": {"entity_id": "payment"},
        },
        {
            "rule_id": "payment-timing",
            "channel": "substantive",
            "salience": 40,
            "anchor": {"start": 125, "end": 185},
            "meta": {"entity_id": "payment"},
        },
        {
            "rule_id": "presence-terms",
            "channel": "presence",
            "anchor": {"start": 10, "end": 20},
        },
        {
            "rule_id": "policy-sla",
            "channel": "policy",
            "salience": 60,
            "anchor": {"start": 400, "end": 450},
        },
    ]

    merged = apply_merge_policy(findings)
    assert [f["rule_id"] for f in merged] == [
        "presence-terms",
        "payment-timing",
        "policy-sla",
    ]
    assert all("agenda_group" not in f for f in merged)
