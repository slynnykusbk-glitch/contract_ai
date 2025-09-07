from insurance_checker import check
from .conftest import load_fixture


def test_cgl_soft_warn():
    text = load_fixture("soft_low_cgl.txt")
    result = check(text)
    entry = next(r for r in result["soft"] if r["key"] == "cgl_limit")
    assert entry["status"] == "WARN" and result["summary"]["soft_warn_count"] >= 1
