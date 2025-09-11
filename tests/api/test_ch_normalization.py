import json
from pathlib import Path

from contract_review_app.api.integrations import _normalize_profile

FIXT = Path("tests/fixtures/ch_blackrock_profile.json")


def test_normalize_blackrock():
    data = json.loads(FIXT.read_text())
    norm = _normalize_profile(data, officers=3, psc=1)
    assert norm["status"] == "active"
    assert norm["company_number"] == "02022650"
    assert norm["registered_office"]["postcode"] == "EC2N 2DL"
    assert norm["officers_count"] == 3
    assert norm["psc_count"] == 1
