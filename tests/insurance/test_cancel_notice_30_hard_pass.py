from insurance_checker import check
from .conftest import load_fixture


def test_cancel_notice_30_hard_pass():
    text = load_fixture("good_master_excerpt.txt")
    result = check(text)
    entry = next(r for r in result["hard"] if r["key"] == "cancel_notice_days")
    assert entry["status"] == "PASS" and result["extract"]["cancel_notice_days"] == 30
