from __future__ import annotations

from hypothesis import given, strategies as st, assume

from contract_review_app.metrics.compute import compute_confusion


@given(
    gold=st.dictionaries(st.text(min_size=1, max_size=5), st.booleans(), max_size=5),
    pred=st.dictionaries(st.text(min_size=1, max_size=5), st.booleans(), max_size=5),
)
def test_rates_clamped(gold, pred):
    metrics = compute_confusion(gold, pred)
    for m in metrics:
        assert 0.0 <= m.precision <= 1.0
        assert 0.0 <= m.recall <= 1.0
        assert 0.0 <= m.f1 <= 1.0


def _f1(tp: int, fp: int, fn: int) -> float:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    denom = prec + rec
    return 2 * prec * rec / denom if denom else 0.0


@given(
    tp1=st.integers(min_value=0, max_value=20),
    tp2=st.integers(min_value=0, max_value=20),
    fp=st.integers(min_value=0, max_value=20),
    fn=st.integers(min_value=0, max_value=20),
)
def test_f1_monotonic(tp1, tp2, fp, fn):
    assume(tp1 <= tp2)
    f1_a = _f1(tp1, fp, fn)
    f1_b = _f1(tp2, fp, fn)
    assert f1_b + 1e-9 >= f1_a
