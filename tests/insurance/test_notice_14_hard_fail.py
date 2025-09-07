from insurance_checker import check
from .conftest import load_fixture


def test_notice_14_hard_fail():
    text = load_fixture("bad_notice_14.txt")
    result = check(text)
    entry = next(r for r in result["hard"] if r["key"] == "cancel_notice_days")
    assert entry["status"] == "FAIL" and result["summary"]["hard_fail_count"] == 1
