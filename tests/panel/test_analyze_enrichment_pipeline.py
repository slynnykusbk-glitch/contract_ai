import os
import respx
import httpx
from fastapi.testclient import TestClient

os.environ.setdefault("FEATURE_INTEGRATIONS", "1")
os.environ.setdefault("FEATURE_COMPANIES_HOUSE", "1")
os.environ.setdefault("COMPANIES_HOUSE_API_KEY", "x")

import importlib
import contract_review_app.config as cfg
import contract_review_app.api.integrations as integrations
import contract_review_app.api.app as app_module
from contract_review_app.integrations.companies_house import client as ch_client

importlib.reload(cfg)
importlib.reload(ch_client)
importlib.reload(integrations)
importlib.reload(app_module)

client = TestClient(app_module.app)
BASE = ch_client.BASE
integrations.CH_API_KEY = "x"
integrations.FEATURE_COMPANIES_HOUSE = "1"


def setup_function():
    ch_client._CACHE.clear()  # type: ignore
    ch_client._LAST.clear()  # type: ignore
    os.makedirs("var", exist_ok=True)
    open("var/audit.log", "w", encoding="utf-8").close()


@respx.mock
def test_enrichment_pipeline(monkeypatch):
    monkeypatch.setattr(integrations, "_ch_gate", lambda: None)
    monkeypatch.setenv("FEATURE_COMPANIES_HOUSE", "1")
    monkeypatch.setenv("CH_API_KEY", "x")
    ch_client.KEY = "x"
    respx.get(f"{BASE}/search/companies").respond(
        json={"items": [{"title": "ACME LTD", "company_number": "321"}]},
        headers={"ETag": "s1"},
    )
    respx.get(f"{BASE}/company/321").respond(
        json={"company_name": "ACME LTD", "company_number": "321"}
    )
    respx.get(f"{BASE}/company/321/officers?items_per_page=1").respond(
        json={"total_results": 5}
    )
    respx.get(
        f"{BASE}/company/321/persons-with-significant-control?items_per_page=1"
    ).respond(json={"total_results": 1})
    resp = client.post(
        "/api/analyze",
        json={"text": "Agreement between Acme Ltd and Foo"},
        headers={"x-api-key": "k", "x-schema-version": "1.4"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["parties"][0]["registry"]["name"] == "ACME LTD"
    assert data["meta"]["companies_meta"][0]["matched"]["company_name"] == "ACME LTD"
    assert data["meta"]["companies_meta"][0]["verdict"] == "ok"
    with open("var/audit.log", encoding="utf-8") as fh:
        assert "integration_call" in fh.read()
