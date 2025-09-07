import os
import respx
import httpx
from fastapi.testclient import TestClient

os.environ.setdefault("FEATURE_INTEGRATIONS", "1")
os.environ.setdefault("FEATURE_COMPANIES_HOUSE", "1")
os.environ.setdefault("COMPANIES_HOUSE_API_KEY", "x")

import contract_review_app.api.app as app_module
from contract_review_app.integrations.companies_house import client as ch_client

client = TestClient(app_module.app)
BASE = ch_client.BASE


def setup_function():
    ch_client._CACHE.clear()  # type: ignore
    ch_client._LAST.clear()  # type: ignore
    os.makedirs("var", exist_ok=True)
    open("var/audit.log", "w").close()


@respx.mock
def test_enrichment_pipeline():
    respx.get(f"{BASE}/search/companies").respond(
        json={"items": [{"title": "ACME LTD", "company_number": "321"}]}, headers={"ETag": "s1"}
    )
    respx.get(f"{BASE}/company/321").respond(json={"company_name": "ACME LTD", "company_number": "321"})
    resp = client.post("/api/analyze", json={"text": "Agreement between Acme Ltd and Foo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["parties"][0]["registry"]["name"] == "ACME LTD"
    with open("var/audit.log") as fh:
        assert "integration_call" in fh.read()
