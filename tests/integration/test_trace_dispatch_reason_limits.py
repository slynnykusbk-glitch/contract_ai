import importlib

from contract_review_app.legal_rules.dispatcher import (
    ReasonAmount,
    ReasonCodeRef,
    ReasonDuration,
    ReasonPattern,
    ReasonPayload,
)


class _DummyCandidate:
    def __init__(self, reason: ReasonPayload) -> None:
        self.rule_id = "rule-1"
        self.gates = {"packs": True, "lang": True, "doctypes": True}
        self.gates_passed = True
        self.expected_any = ["trigger"]
        self.matched = []
        self.reasons = (reason,)
        self.reason = None
        self.channel = "default"
        self.salience = 10


def _make_offsets(count: int, base: int = 0) -> tuple[tuple[int, int], ...]:
    return tuple((base + idx * 10, base + idx * 10 + 5) for idx in range(count))


def test_trace_dispatch_reason_offsets_are_limited(monkeypatch):
    monkeypatch.setenv("TRACE_REASON_MAX_OFFSETS_PER_TYPE", "4")

    from contract_review_app import trace_artifacts as trace_mod

    importlib.reload(trace_mod)

    try:
        reason = ReasonPayload(
            labels=("amount", "duration", "law", "jurisdiction", "pattern"),
            patterns=(
                ReasonPattern(kind="keyword", offsets=_make_offsets(3)),
                ReasonPattern(kind="regex", offsets=_make_offsets(3, 100)),
            ),
            amounts=(
                ReasonAmount(currency="USD", value=1000, offsets=_make_offsets(5)),
            ),
            durations=(
                ReasonDuration(unit="days", value=30, offsets=_make_offsets(5, 200)),
            ),
            law=(ReasonCodeRef(code="US", offsets=_make_offsets(5, 400)),),
            jurisdiction=(ReasonCodeRef(code="US", offsets=_make_offsets(5, 600)),),
        )

        dispatch = trace_mod.build_dispatch(1, 1, 1, (_DummyCandidate(reason),))

        candidates = dispatch.get("candidates") or []
        assert candidates, "expected candidates payload"

        reasons = candidates[0].get("reasons") or []
        assert reasons, "expected reasons payload"

        payload = reasons[0]
        limit = 4

        buckets = ("patterns", "amounts", "durations", "law", "jurisdiction")
        seen_capped = False

        for bucket in buckets:
            entries = payload.get(bucket) or []
            assert isinstance(entries, list)
            total_offsets = 0
            for entry in entries:
                offsets = entry.get("offsets") or []
                assert isinstance(offsets, list)
                assert offsets, "expected offsets to remain after limiting"
                total_offsets += len(offsets)
                for span in offsets:
                    assert isinstance(span, list)
                    assert len(span) == 2
                    assert all(isinstance(value, int) for value in span)
                lowered_keys = {str(key).lower() for key in entry.keys()}
                assert "text" not in lowered_keys
            assert total_offsets <= limit
            if total_offsets == limit:
                seen_capped = True

        assert seen_capped, "expected at least one bucket to hit the limit"
    finally:
        monkeypatch.delenv("TRACE_REASON_MAX_OFFSETS_PER_TYPE", raising=False)
        importlib.reload(trace_mod)
