from __future__ import annotations

import copy
import random

from contract_review_app.legal_rules.aggregate import apply_merge_policy


GROUPS = ["presence", "substantive", "policy", "law", "drafting"]

BASE_FINDINGS = [
    {
        "rule_id": f"{group}-{idx}",
        "channel": group,
        "salience": 90 - idx,
        "anchor": {"start": idx * 50 + order * 5, "end": idx * 50 + order * 5 + 12},
    }
    for idx in range(10)
    for order, group in enumerate(GROUPS)
]


def test_permutation_stability():
    expected = apply_merge_policy(copy.deepcopy(BASE_FINDINGS), use_agenda=True)
    expected_order = [f["rule_id"] for f in expected]

    rng = random.Random(42)
    for _ in range(5):
        permuted = copy.deepcopy(BASE_FINDINGS)
        rng.shuffle(permuted)
        result = apply_merge_policy(permuted, use_agenda=True)
        assert [f["rule_id"] for f in result] == expected_order
