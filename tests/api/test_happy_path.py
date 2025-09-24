import os
from fastapi.testclient import TestClient
import respx
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION
from contract_review_app.integrations.companies_house import client as ch_client

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("FEATURE_COMPANIES_HOUSE", "1")
os.environ.setdefault("CH_API_KEY", "x")
ch_client.KEY = "x"
client = TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})
BASE = ch_client.BASE


@respx.mock
def test_end_to_end_happy_path():
    respx.get(f"{BASE}/search/companies").respond(
        json={"items": []}, headers={"ETag": "e1"}
    )
    r_analyze = client.post("/api/analyze", json={"text": "hello world"})
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    r_summary = client.post("/api/summary", json={"cid": cid})
    assert r_summary.status_code == 200
    r_comp = client.post("/api/companies/search", json={"query": "ACME"})
    assert r_comp.status_code == 200
