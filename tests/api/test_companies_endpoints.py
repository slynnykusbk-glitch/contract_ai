import os
import httpx
import respx
from fastapi.testclient import TestClient

os.environ.setdefault("FEATURE_INTEGRATIONS", "1")
os.environ.setdefault("FEATURE_COMPANIES_HOUSE", "1")
os.environ.setdefault("CH_API_KEY", "x")

import contract_review_app.api.app as app_module
from contract_review_app.integrations.companies_house import client as ch_client

client = TestClient(app_module.app)
BASE = ch_client.BASE
ch_client.KEY = "x"
os.environ["FEATURE_COMPANIES_HOUSE"] = "1"


@respx.mock
def test_search_endpoint():
    respx.get(f"{BASE}/search/companies").respond(json={"items": []}, headers={"ETag": "s1"})
    r = client.post("/api/companies/search", json={"query": "ACME"})
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.headers.get("ETag") == "s1"
    assert r.headers.get("x-cache") == "miss"
    r2 = client.get("/api/companies/search", params={"q": "ACME"})
    assert r2.status_code == 200


@respx.mock
def test_profile_endpoint():
    respx.get(f"{BASE}/company/42").respond(json={"company_name": "ACME"}, headers={"ETag": "p1"})
    r = client.get("/api/companies/42")
    assert r.status_code == 200
    assert r.json()["company_name"] == "ACME"


def test_disabled(monkeypatch):
    monkeypatch.setenv("FEATURE_COMPANIES_HOUSE", "0")
    import importlib
    import contract_review_app.config as cfg
    import contract_review_app.api.integrations as integrations
    import contract_review_app.integrations.companies_house.client as ch_client
    import contract_review_app.api.app as app_module
    importlib.reload(cfg)
    importlib.reload(ch_client)
    importlib.reload(integrations)
    importlib.reload(app_module)
    local_client = TestClient(app_module.app)
    r = local_client.post("/api/companies/search", json={"query": "A"})
    assert r.status_code == 503
    monkeypatch.setenv("FEATURE_COMPANIES_HOUSE", "1")
    importlib.reload(cfg)
    importlib.reload(ch_client)
    importlib.reload(integrations)
    importlib.reload(app_module)


@respx.mock
def test_etag_round_trip():
    url = f"{BASE}/company/77"
    respx.get(url).mock(side_effect=[
        httpx.Response(200, json={"company_name": "AC"}, headers={"ETag": "e3"}),
        httpx.Response(304, headers={"ETag": "e3"}),
    ])
    r1 = client.get("/api/companies/77")
    assert r1.status_code == 200
    etag = r1.headers.get("ETag")
    assert r1.headers.get("x-cache") == "miss"
    r2 = client.get("/api/companies/77", headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.headers.get("x-cache") == "hit"
