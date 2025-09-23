import itertools

from contract_review_app.legal_rules.aggregate import apply_legacy_merge_policy


def _finding(
    channel: str,
    severity: str = "medium",
    start: int = 0,
    end: int = 10,
    rule_id: str = "R-001",
    snippet: str | None = None,
) -> dict:
    return {
        "channel": channel,
        "severity": severity,
        "start": start,
        "end": end,
        "rule_id": rule_id,
        "snippet": snippet if snippet is not None else "x" * max(end - start, 1),
    }


def test_channel_priority_beats_other_attributes():
    law_finding = _finding("Law", severity="medium", rule_id="LAW")
    policy_finding = _finding("Policy", severity="critical", rule_id="POL")

    merged = apply_legacy_merge_policy([policy_finding, law_finding])

    assert len(merged) == 1
    assert merged[0]["rule_id"] == "LAW"


def test_severity_breaks_ties_within_channel():
    low = _finding("Policy", severity="medium", rule_id="POL-LOW")
    high = _finding("Policy", severity="critical", rule_id="POL-HIGH")

    merged = apply_legacy_merge_policy([low, high])

    assert len(merged) == 1
    assert merged[0]["rule_id"] == "POL-HIGH"


def test_snippet_length_breaks_severity_ties():
    shorter = _finding("Policy", severity="medium", snippet="short", rule_id="S1")
    longer = _finding("Policy", severity="medium", snippet="longer text", rule_id="L1")

    merged = apply_legacy_merge_policy([shorter, longer])

    assert len(merged) == 1
    assert merged[0]["rule_id"] == "L1"


def test_rule_id_breaks_all_other_ties():
    first = _finding("Policy", severity="medium", rule_id="A")
    second = _finding("Policy", severity="medium", rule_id="B")

    merged = apply_legacy_merge_policy([second, first])

    assert len(merged) == 1
    assert merged[0]["rule_id"] == "A"


def test_overlapping_spans_preserve_best_per_span():
    dominant = _finding("Law", severity="medium", start=0, end=10, rule_id="LAW")
    weaker = _finding("Policy", severity="medium", start=0, end=10, rule_id="POL")
    other = _finding("Substantive", severity="medium", start=5, end=15, rule_id="SUB")

    merged = apply_legacy_merge_policy([weaker, other, dominant])

    assert [f["rule_id"] for f in merged] == ["LAW", "SUB"]


def test_merge_policy_is_deterministic():
    base = [
        _finding("Policy", severity="medium", start=0, end=10, rule_id="P1"),
        _finding("Law", severity="medium", start=0, end=10, rule_id="L1"),
        _finding("Grammar", severity="low", start=20, end=30, rule_id="G1"),
    ]

    expected = apply_legacy_merge_policy(base)
    for perm in itertools.permutations(base):
        assert apply_legacy_merge_policy(list(perm)) == expected
