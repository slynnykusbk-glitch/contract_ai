from insurance_checker import check
from .conftest import load_fixture


def test_goods_ins_soft_warn():
    text = load_fixture("soft_no_goods_ins.txt")
    result = check(text)
    entry = next(r for r in result["soft"] if r["key"] == "goods_transit_required")
    assert entry["status"] == "WARN" and result["summary"]["soft_warn_count"] >= 1
