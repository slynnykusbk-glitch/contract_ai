from insurance_checker import check
from .conftest import load_fixture


def test_failure_to_insure_terminate_hard_pass():
    text = load_fixture("good_master_excerpt.txt")
    result = check(text)
    entry = next(r for r in result["hard"] if r["key"] == "failure_to_insure_remedy")
    assert entry["status"] == "PASS"
    assert "terminate" in result["extract"]["failure_to_insure_remedy"]
