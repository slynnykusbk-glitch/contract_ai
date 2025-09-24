from insurance_checker import check
from .conftest import load_fixture


def test_certs_provision_hard_pass():
    text = load_fixture("good_master_excerpt.txt")
    result = check(text)
    assert any(
        r["key"] == "certs_provision" and r["status"] == "PASS" for r in result["hard"]
    )
