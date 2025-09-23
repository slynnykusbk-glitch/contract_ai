import statistics
import time

from contract_review_app.legal_rules import coverage_map


def test_build_coverage_perf_smoke():
    coverage_map.invalidate_cache()
    cmap = coverage_map.load_coverage_map()
    assert cmap is not None

    segments = []
    candidates = []
    for idx in range(300):
        start = idx * 100
        segments.append(
            {
                "labels": ["payment", "invoice"],
                "entities": {
                    "amounts": [1, 2, 3],
                    "durations": [{"value": {"days": 30}}],
                },
                "span": [start, start + 80],
            }
        )
        candidates.append({"pay_late_interest_v1", "pay_terms_clear_v2"})

    triggered = {"pay_late_interest_v1"}
    rule_lookup = {rid: {} for rid in ["pay_late_interest_v1", "pay_terms_clear_v2"]}

    # warm-up
    coverage_map.build_coverage(segments, candidates, triggered, rule_lookup)

    timings = []
    for _ in range(3):
        start = time.perf_counter()
        coverage_map.build_coverage(segments, candidates, triggered, rule_lookup)
        timings.append(time.perf_counter() - start)

    avg = statistics.mean(timings)
    assert avg < 0.05, f"build_coverage is too slow: {avg:.4f}s"
