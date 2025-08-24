from contract_review_app.report.metrics import summarize_statuses


def test_summarize_basic_counts_and_pct():
    results = [
        {"status": "OK"},
        {"status": "WARN"},
        {"status": "FAIL"},
        {"status": "OK"},
    ]
    m = summarize_statuses(results)
    assert m["total"] == 4
    assert m["ok"] == 2 and round(m["ok_pct"], 1) == 50.0
    assert m["warn"] == 1 and round(m["warn_pct"], 1) == 25.0
    assert m["fail"] == 1 and round(m["fail_pct"], 1) == 25.0


def test_empty_input():
    m = summarize_statuses([])
    assert m["total"] == 0
    assert m["ok"] == 0 and m["ok_pct"] == 0.0
    assert m["warn"] == 0 and m["warn_pct"] == 0.0
    assert m["fail"] == 0 and m["fail_pct"] == 0.0
