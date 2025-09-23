from __future__ import annotations

import copy

from contract_review_app.analysis.agenda import agenda_sort_key, span_iou
from contract_review_app.legal_rules.aggregate import apply_merge_policy


def _span(finding: dict) -> tuple[int, int] | None:
    anchor = finding.get("anchor")
    if not isinstance(anchor, dict):
        return None
    start = anchor.get("start")
    end = anchor.get("end")
    if isinstance(start, int) and isinstance(end, int):
        return start, end
    return None


def _overlap_pairs(findings: list[dict]) -> int:
    total = 0
    for idx, current in enumerate(findings):
        span_a = _span(current)
        if span_a is None:
            continue
        for other in findings[idx + 1 :]:
            span_b = _span(other)
            if span_b is None:
                continue
            if span_iou(span_a, span_b) >= 0.6:
                total += 1
    return total


def test_panel_order_visible():
    findings = [
        {
            "rule_id": "presence-primary",
            "channel": "presence",
            "salience": 95,
            "anchor": {"start": 10, "end": 70},
        },
        {
            "rule_id": "presence-secondary",
            "channel": "presence",
            "salience": 70,
            "anchor": {"start": 12, "end": 68},
        },
        {
            "rule_id": "policy-duplicate",
            "channel": "policy",
            "salience": 65,
            "anchor": {"start": 120, "end": 180},
        },
        {
            "rule_id": "policy-weak",
            "channel": "policy",
            "salience": 40,
            "anchor": {"start": 118, "end": 182},
        },
        {
            "rule_id": "substantive-gap",
            "channel": "substantive",
            "salience": 80,
            "anchor": {"start": 80, "end": 110},
        },
    ]

    legacy = apply_merge_policy(copy.deepcopy(findings), use_agenda=False)
    agenda = apply_merge_policy(copy.deepcopy(findings), use_agenda=True)

    assert _overlap_pairs(agenda) < _overlap_pairs(legacy)
    assert [f["rule_id"] for f in agenda] == [
        f["rule_id"] for f in sorted(copy.deepcopy(agenda), key=agenda_sort_key)
    ]
    assert all("agenda_group" not in f for f in agenda)
