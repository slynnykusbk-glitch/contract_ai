from __future__ import annotations

import copy

from contract_review_app.legal_rules.aggregate import apply_merge_policy


def _finding(**kwargs):
    base = {
        "rule_id": kwargs.get("rule_id", "rule"),
        "anchor": {"start": kwargs.get("start", 0), "end": kwargs.get("end", 1)},
    }
    base.update(kwargs)
    base.setdefault("anchor", {"start": kwargs.get("start", 0), "end": kwargs.get("end", 1)})
    return base


def test_order_by_group_then_salience_then_start_then_rule():
    findings = [
        _finding(
            rule_id="policy-1",
            channel="policy",
            salience=70,
            start=300,
            end=320,
        ),
        _finding(
            rule_id="presence-02",
            channel="presence",
            salience=95,
            start=200,
            end=210,
        ),
        _finding(
            rule_id="presence-01",
            channel="presence",
            salience=95,
            start=100,
            end=110,
        ),
        _finding(
            rule_id="presence-00",
            channel="presence",
            salience=95,
            start=100,
            end=110,
        ),
        _finding(
            rule_id="presence-low",
            channel="presence",
            salience=90,
            start=400,
            end=420,
        ),
        _finding(
            rule_id="substantive-1",
            channel="substantive",
            salience=80,
            start=10,
            end=30,
        ),
    ]

    ordered = apply_merge_policy(copy.deepcopy(findings))
    assert [f["rule_id"] for f in ordered] == [
        "presence-00",
        "presence-01",
        "presence-02",
        "presence-low",
        "substantive-1",
        "policy-1",
    ]


def test_salience_defaults_by_group():
    cases = {
        "presence-default": ("presence", None, 95),
        "substantive-default": ("substantive", None, 80),
        "policy-default": ("policy", None, 70),
        "law-default": ("law", None, 70),
        "drafting-default": ("drafting", None, 40),
        "grammar-default": ("grammar", None, 20),
        "fixup-default": ("fixup", None, 10),
        "policy-high-clamp": ("policy", 150, 100),
        "grammar-low-clamp": ("grammar", -5, 0),
    }

    findings = [
        {
            "rule_id": rule_id,
            "channel": channel,
            "salience": salience,
            "anchor": {"start": idx * 50, "end": idx * 50 + 10},
        }
        for idx, (rule_id, (channel, salience, _)) in enumerate(cases.items())
    ]

    merged = apply_merge_policy(copy.deepcopy(findings))
    by_rule = {f["rule_id"]: f["salience"] for f in merged}

    for rule_id, (_, __, expected) in cases.items():
        assert by_rule[rule_id] == expected
