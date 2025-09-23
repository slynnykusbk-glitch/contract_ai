from __future__ import annotations

import time

from contract_review_app.legal_rules.aggregate import apply_merge_policy


def test_merge_perf_5k_findings():
    findings = [
        {
            "rule_id": f"rule-{idx}",
            "channel": "substantive" if idx % 3 else "policy",
            "salience": (idx % 100),
            "anchor": {"start": idx * 5, "end": idx * 5 + 3},
        }
        for idx in range(5000)
    ]

    start = time.perf_counter()
    merged = apply_merge_policy(findings)
    duration = time.perf_counter() - start

    assert len(merged) == len(findings)
    assert duration < 8.0
