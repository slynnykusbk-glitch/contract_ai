from insurance_checker import check
from .conftest import load_fixture


def test_flowdown_soft_warn():
    text = load_fixture("soft_no_flowdown.txt")
    result = check(text)
    entry = next(r for r in result["soft"] if r["key"] == "flowdown_to_subs")
    assert entry["status"] == "WARN" and result["summary"]["soft_warn_count"] >= 1
