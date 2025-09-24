from insurance_checker import check
from .conftest import load_fixture


def test_primary_noncontrib_hard_pass():
    text = load_fixture("good_master_excerpt.txt")
    result = check(text)
    assert any(
        r["key"] == "primary_noncontrib" and r["status"] == "PASS"
        for r in result["hard"]
    )
