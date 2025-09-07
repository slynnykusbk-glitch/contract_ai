from insurance_checker import check
from .conftest import load_fixture


def test_ai_missing_hard_fail():
    text = load_fixture("bad_missing_ai.txt")
    result = check(text)
    entry = next(r for r in result["hard"] if r["key"] == "additional_insured")
    assert entry["status"] == "FAIL"
    assert result["summary"]["hard_fail_count"] == 1
