from insurance_checker import check
from .conftest import load_fixture


def test_runoff_soft_warn():
    text = load_fixture("soft_no_runoff.txt")
    result = check(text)
    entry = next(r for r in result["soft"] if r["key"] == "claims_made_runoff")
    assert entry["status"] == "WARN" and result["summary"]["soft_warn_count"] >= 1
