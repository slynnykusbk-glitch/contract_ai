from __future__ import annotations

from contract_review_app.legal_rules.aggregate import apply_merge_policy


def _finding(rule_id: str, channel: str, salience: int, start: int, end: int) -> dict:
    return {
        "rule_id": rule_id,
        "channel": channel,
        "salience": salience,
        "anchor": {"start": start, "end": end},
    }


def test_overlap_same_group_keeps_strongest():
    dominant = _finding("duplicate-rule", "substantive", 90, 0, 120)
    weaker = _finding("duplicate-rule", "substantive", 40, 5, 125)

    merged = apply_merge_policy([weaker, dominant], use_agenda=True)
    assert [f["rule_id"] for f in merged] == ["duplicate-rule"]
    assert merged[0]["salience"] == 90


def test_overlap_diff_groups_keep_both_when_strict_off():
    presence = _finding("presence-check", "presence", 95, 0, 50)
    substantive = _finding("sub-check", "substantive", 80, 10, 60)

    merged = apply_merge_policy([substantive, presence], use_agenda=True)
    assert {f["rule_id"] for f in merged} == {"presence-check", "sub-check"}


def test_overlap_diff_groups_single_when_strict_on(monkeypatch):
    monkeypatch.setenv("FEATURE_AGENDA_STRICT_MERGE", "1")
    presence = _finding("presence-check", "presence", 95, 0, 50)
    substantive = _finding("sub-check", "substantive", 80, 10, 60)

    merged = apply_merge_policy([substantive, presence], use_agenda=True)
    assert [f["rule_id"] for f in merged] == ["presence-check"]
