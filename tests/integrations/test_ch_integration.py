import json
import os

import respx
from contract_review_app.core.schemas import Party
from contract_review_app.integrations.service import build_companies_meta
from contract_review_app.integrations.companies_house import client as ch_client

FIXT = json.loads(open("tests/fixtures/ch_blackrock_profile.json", "r", encoding="utf-8").read())
BASE = ch_client.BASE


def setup_function():
    os.environ["FEATURE_COMPANIES_HOUSE"] = "1"
    os.environ["CH_API_KEY"] = "x"
    ch_client.KEY = "x"
    ch_client._CACHE.clear()  # type: ignore
    ch_client._LAST.clear()  # type: ignore


@respx.mock
def test_build_companies_meta_blackrock():
    respx.get(f"{BASE}/company/02022650").respond(json=FIXT)
    respx.get(f"{BASE}/company/02022650/officers?items_per_page=1").respond(json={"total_results": 1})
    respx.get(
        f"{BASE}/company/02022650/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 0})
    p = Party(name="BLACK ROCK (UK) LIMITED", company_number="02022650")
    meta = build_companies_meta([p])
    assert meta[0]["matched"]["company_number"] == "02022650"
    assert meta[0]["verdict"] == "ok"
