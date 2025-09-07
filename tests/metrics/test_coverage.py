from __future__ import annotations

from contract_review_app.metrics.compute import compute_coverage


def test_coverage_basic():
    inventory = {"r1", "r2", "r3"}
    fired = {"r1", "r3"}
    cov = compute_coverage(inventory, fired)
    assert cov.rules_total == 3
    assert cov.rules_fired == 2
    assert abs(cov.coverage - 2 / 3) < 1e-9


def test_coverage_empty():
    cov = compute_coverage(set(), set())
    assert cov.rules_total == 0
    assert cov.coverage == 0.0
