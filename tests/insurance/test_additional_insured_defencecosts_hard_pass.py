from insurance_checker import check
from .conftest import load_fixture


def test_additional_insured_defencecosts_hard_pass():
    text = load_fixture("good_master_excerpt.txt")
    result = check(text)
    assert any(
        r["key"] == "additional_insured" and r["status"] == "PASS"
        for r in result["hard"]
    )
