from __future__ import annotations

import copy
import time

from contract_review_app.legal_rules.aggregate import apply_merge_policy


def test_merge_perf_5k_findings():
    findings = [
        {
            "rule_id": f"rule-{idx}",
            "channel": "substantive" if idx % 3 else "policy",
            "salience": (idx % 120) - 10,
            "anchor": {"start": idx * 5, "end": idx * 5 + 4},
        }
        for idx in range(5000)
    ]

    baseline_start = time.perf_counter()
    apply_merge_policy(copy.deepcopy(findings), use_agenda=False)
    baseline_duration = max(time.perf_counter() - baseline_start, 1e-6)

    agenda_start = time.perf_counter()
    merged = apply_merge_policy(copy.deepcopy(findings), use_agenda=True)
    agenda_duration = max(time.perf_counter() - agenda_start, 0.0)

    assert len(merged) == len(findings)
    # The agenda-aware merge performs additional grouping and overlap checks, so we
    # keep the relative slowdown bounded while enforcing a tight absolute limit.
    assert agenda_duration <= baseline_duration * 2 + 0.02
    assert agenda_duration <= 0.150
