import importlib

from contract_review_app.legal_rules.dispatcher import ReasonPattern, ReasonPayload


class _DummyCandidate:
    def __init__(self, idx: int, reasons: tuple[ReasonPayload, ...]):
        self.rule_id = f"rule-{idx}"
        self.gates = {"packs": True, "lang": True, "doctypes": True}
        self.gates_passed = True
        self.expected_any = [f"trigger-{idx}"]
        self.matched = [
            {
                "start": idx,
                "end": idx + 1,
                "pattern_id": f"pat-{idx}",
            }
        ]
        self.reasons = reasons
        self.reason = None
        self.channel = f"channel-{idx}"
        self.salience = 10 + idx


def _make_reason(rule_idx: int, reason_idx: int) -> ReasonPayload:
    return ReasonPayload(
        labels=(f"label-{rule_idx}-{reason_idx}",),
        patterns=(
            ReasonPattern(
                kind="keyword",
                offsets=((reason_idx, reason_idx + rule_idx + 1),),
            ),
        ),
        gates=(("packs", reason_idx % 2 == 0), ("lang", True)),
    )


def test_dispatch_trace_limits_and_reason_shape(monkeypatch):
    monkeypatch.setenv("DISPATCH_MAX_CANDIDATES_PER_SEGMENT", "3")
    monkeypatch.setenv("DISPATCH_MAX_REASONS_PER_RULE", "2")

    from contract_review_app import trace_artifacts as trace_mod

    importlib.reload(trace_mod)

    try:
        candidates = []
        for idx in range(6):
            reasons = tuple(_make_reason(idx, r) for r in range(5))
            candidates.append(_DummyCandidate(idx, reasons))

        dispatch = trace_mod.build_dispatch(10, 9, 4, candidates)

        candidates_payload = dispatch.get("candidates") or []
        assert len(candidates_payload) == 3

        for entry in candidates_payload:
            reasons_payload = entry.get("reasons") or []
            assert len(reasons_payload) <= 2
            for reason in reasons_payload:
                assert "labels" in reason
                assert "patterns" in reason
                assert "gates" in reason
                assert isinstance(reason["labels"], list)
                assert isinstance(reason["patterns"], list)
                assert isinstance(reason["gates"], dict)
                for pattern in reason["patterns"]:
                    assert pattern.get("kind") in {"regex", "keyword"}
                    assert isinstance(pattern.get("offsets"), list)

        expected_meta = {
            f"rule-{idx}": {"channel": f"channel-{idx}", "salience": 10 + idx}
            for idx in range(3)
        }
        for entry in candidates_payload:
            rule_id = entry.get("rule_id")
            assert rule_id in expected_meta
            assert entry.get("channel") == expected_meta[rule_id]["channel"]
            assert entry.get("salience") == expected_meta[rule_id]["salience"]
    finally:
        monkeypatch.delenv("DISPATCH_MAX_CANDIDATES_PER_SEGMENT", raising=False)
        monkeypatch.delenv("DISPATCH_MAX_REASONS_PER_RULE", raising=False)
        importlib.reload(trace_mod)
