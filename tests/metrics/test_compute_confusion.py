from __future__ import annotations

from contract_review_app.metrics.compute import compute_confusion


def test_confusion_counts():
    gold = {"r1": True, "r2": True, "r3": False}
    pred = {"r1": True, "r2": False, "r3": True}
    metrics = {m.rule_id: m for m in compute_confusion(gold, pred)}
    assert metrics["r1"].tp == 1 and metrics["r1"].fp == 0 and metrics["r1"].fn == 0
    assert metrics["r2"].tp == 0 and metrics["r2"].fn == 1
    assert metrics["r3"].fp == 1 and metrics["r3"].fn == 0
    assert metrics["r1"].f1 == 1.0


def test_confusion_empty():
    assert compute_confusion({}, {}) == []
