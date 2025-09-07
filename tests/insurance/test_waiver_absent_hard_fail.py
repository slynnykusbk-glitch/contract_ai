from insurance_checker import check
from .conftest import load_fixture


def test_waiver_absent_hard_fail():
    text = load_fixture("bad_waiver_absent.txt")
    result = check(text)
    entry = next(r for r in result["hard"] if r["key"] == "waiver_subrogation")
    assert entry["status"] == "FAIL" and result["summary"]["hard_fail_count"] == 1
