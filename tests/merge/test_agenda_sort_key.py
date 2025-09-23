from __future__ import annotations

import copy

from contract_review_app.legal_rules.aggregate import apply_merge_policy


def _finding(
    rule_id: str,
    *,
    channel: str | None = None,
    salience: int | None = None,
    start: int = 0,
    end: int | None = None,
) -> dict:
    anchor_end = end if end is not None else start + 10
    payload = {
        "rule_id": rule_id,
        "anchor": {"start": start, "end": anchor_end},
    }
    if channel is not None:
        payload["channel"] = channel
    if salience is not None:
        payload["salience"] = salience
    return payload


def test_order_by_group_salience_start_rule():
    findings = [
        _finding("presence-default", channel="presence", start=100),
        _finding("presence-explicit", channel="presence", salience=90, start=300),
        _finding("substantive-strong", channel="substantive", salience=82, start=50),
        _finding("policy-item", channel="policy", salience=70, start=400),
        _finding("law-companion", channel="law", salience=60, start=410),
        _finding("drafting-style", channel="style", salience=45, start=20),
    ]

    ordered = apply_merge_policy(copy.deepcopy(findings), use_agenda=True)

    assert [f["rule_id"] for f in ordered] == [
        "presence-default",
        "presence-explicit",
        "substantive-strong",
        "policy-item",
        "law-companion",
        "drafting-style",
    ]


def test_salience_defaults_and_clamp():
    cases = {
        "presence-default": {"channel": "presence"},
        "substantive-default": {"channel": "substantive"},
        "policy-default": {"channel": "policy"},
        "law-default": {"channel": "law"},
        "drafting-default": {"channel": "drafting"},
        "grammar-default": {"channel": "grammar"},
        "fixup-default": {"channel": "fixup"},
        "policy-high": {"channel": "policy", "salience": 150},
        "grammar-low": {"channel": "grammar", "salience": -10},
    }

    findings = [
        _finding(
            rule_id,
            channel=attrs.get("channel"),
            salience=attrs.get("salience"),
            start=idx * 40,
            end=idx * 40 + 10,
        )
        for idx, (rule_id, attrs) in enumerate(cases.items())
    ]

    merged = apply_merge_policy(copy.deepcopy(findings), use_agenda=True)
    salience_by_rule = {f["rule_id"]: f["salience"] for f in merged}

    expected = {
        "presence-default": 95,
        "substantive-default": 80,
        "policy-default": 70,
        "law-default": 70,
        "drafting-default": 40,
        "grammar-default": 20,
        "fixup-default": 10,
        "policy-high": 100,
        "grammar-low": 0,
    }

    for rule_id, value in expected.items():
        assert salience_by_rule[rule_id] == value
