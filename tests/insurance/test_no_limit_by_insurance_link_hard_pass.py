from insurance_checker import check
from .conftest import load_fixture


def test_no_limit_by_insurance_link_hard_pass():
    text = load_fixture("good_master_excerpt.txt")
    result = check(text)
    assert any(r["key"] == "no_limit_by_insurance" and r["status"] == "PASS" for r in result["hard"])
