from __future__ import annotations

import copy
import itertools

from contract_review_app.legal_rules.aggregate import apply_merge_policy


BASE_FINDINGS = [
    {
        "rule_id": "presence-1",
        "channel": "presence",
        "salience": 95,
        "anchor": {"start": 10, "end": 20},
    },
    {
        "rule_id": "substantive-1",
        "channel": "substantive",
        "salience": 80,
        "anchor": {"start": 200, "end": 220},
    },
    {
        "rule_id": "policy-1",
        "channel": "policy",
        "salience": 70,
        "anchor": {"start": 400, "end": 410},
    },
    {
        "rule_id": "presence-2",
        "channel": "presence",
        "salience": 90,
        "anchor": {"start": 50, "end": 60},
    },
]


def test_permutation_stability():
    expected = apply_merge_policy(copy.deepcopy(BASE_FINDINGS))
    expected_order = [f["rule_id"] for f in expected]

    for perm in itertools.permutations(BASE_FINDINGS):
        result = apply_merge_policy(copy.deepcopy(list(perm)))
        assert [f["rule_id"] for f in result] == expected_order
