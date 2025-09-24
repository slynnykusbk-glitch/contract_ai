from __future__ import annotations

import copy

from contract_review_app.analysis.agenda import agenda_sort_key
from contract_review_app.legal_rules.aggregate import apply_merge_policy


def _fingerprint(
    findings: list[dict],
) -> list[tuple[str | None, int | None, int | None]]:
    result: list[tuple[str | None, int | None, int | None]] = []
    for finding in findings:
        anchor = finding.get("anchor") or {}
        start = anchor.get("start") if isinstance(anchor, dict) else None
        end = anchor.get("end") if isinstance(anchor, dict) else None
        result.append(
            (
                finding.get("rule_id"),
                start if isinstance(start, int) else None,
                end if isinstance(end, int) else None,
            )
        )
    return result


def test_backend_order_is_deterministic() -> None:
    findings = [
        {
            "rule_id": "presence-primary",
            "channel": "presence",
            "salience": 95,
            "anchor": {"start": 0, "end": 12},
        },
        {
            "rule_id": "substantive-gap",
            "channel": "substantive",
            "salience": 80,
            "anchor": {"start": 40, "end": 60},
        },
        {
            "rule_id": "policy-warning",
            "channel": "policy",
            "salience": 75,
            "anchor": {"start": 80, "end": 100},
        },
        {
            "rule_id": "policy-low",
            "channel": "policy",
            "salience": 65,
            "anchor": {"start": 120, "end": 140},
        },
        {
            "rule_id": "drafting-typo",
            "channel": "drafting",
            "salience": 30,
            "anchor": {"start": 160, "end": 170},
        },
    ]

    shuffled = [findings[3], findings[1], findings[4], findings[0], findings[2]]

    ordered = apply_merge_policy(copy.deepcopy(findings), use_agenda=True)
    reordered = apply_merge_policy(copy.deepcopy(shuffled), use_agenda=True)

    assert _fingerprint(ordered) == _fingerprint(reordered)
    assert _fingerprint(ordered) == _fingerprint(
        sorted(copy.deepcopy(ordered), key=agenda_sort_key)
    )
