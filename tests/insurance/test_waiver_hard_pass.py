from insurance_checker import check
from .conftest import load_fixture


def test_waiver_hard_pass():
    text = load_fixture("good_master_excerpt.txt")
    result = check(text)
    assert any(
        r["key"] == "waiver_subrogation" and r["status"] == "PASS"
        for r in result["hard"]
    )
