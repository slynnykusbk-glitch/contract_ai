from __future__ import annotations

from contract_review_app.legal_rules.aggregate import apply_merge_policy


def _finding(rule_id: str, channel: str, salience: int, start: int, end: int, *, meta=None):
    payload = {
        "rule_id": rule_id,
        "channel": channel,
        "salience": salience,
        "anchor": {"start": start, "end": end},
    }
    if meta:
        payload["meta"] = meta
    return payload


def test_overlap_keeps_strongest_same_group():
    dominant = _finding("duplicate-rule", "substantive", 90, 0, 100, meta={"entity_id": "payment"})
    weaker = _finding("duplicate-rule", "substantive", 50, 10, 110, meta={"entity_id": "payment"})

    merged = apply_merge_policy([weaker, dominant])
    assert [f["rule_id"] for f in merged] == ["duplicate-rule"]
    assert merged[0]["salience"] == 90


def test_overlap_different_groups_not_removed_in_strict_off():
    presence = _finding("presence-check", "presence", 95, 0, 50)
    substantive = _finding("sub-check", "substantive", 80, 10, 60)

    merged = apply_merge_policy([substantive, presence])
    assert {f["rule_id"] for f in merged} == {"presence-check", "sub-check"}


def test_overlap_removed_when_strict_merge_on():
    presence = _finding("presence-check", "presence", 95, 0, 50)
    substantive = _finding("sub-check", "substantive", 80, 10, 60)

    merged = apply_merge_policy([substantive, presence], strict_merge=True)
    assert [f["rule_id"] for f in merged] == ["presence-check"]
