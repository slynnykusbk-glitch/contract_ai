import importlib
from fastapi.testclient import TestClient
import respx
import httpx


def make_client(monkeypatch, flag="1", key="k"):
    if flag is not None:
        monkeypatch.setenv("FEATURE_COMPANIES_HOUSE", flag)
    else:
        monkeypatch.delenv("FEATURE_COMPANIES_HOUSE", raising=False)
    if key is not None:
        monkeypatch.setenv("CH_API_KEY", key)
    else:
        monkeypatch.delenv("CH_API_KEY", raising=False)
    monkeypatch.setenv("FEATURE_INTEGRATIONS", "1")
    import contract_review_app.config as cfg
    import contract_review_app.integrations.companies_house.client as ch_client
    import contract_review_app.api.integrations as integrations
    import contract_review_app.api.app as app_module
    importlib.reload(cfg)
    importlib.reload(ch_client)
    importlib.reload(integrations)
    importlib.reload(app_module)
    client = TestClient(app_module.app)
    return client, ch_client


def _expect_503(client):
    r = client.post("/api/companies/search", json={"q": "AC"})
    assert r.status_code == 503
    assert r.json()["error"] == "companies_house_disabled"
    r2 = client.get("/api/companies/1")
    assert r2.status_code == 503
    assert r2.json()["error"] == "companies_house_disabled"


def test_gate_disabled_no_flag(monkeypatch):
    client, _ = make_client(monkeypatch, flag="0", key="x")
    _expect_503(client)


def test_gate_disabled_no_key(monkeypatch):
    client, _ = make_client(monkeypatch, flag="1", key=None)
    _expect_503(client)


@respx.mock
def test_search_ok(monkeypatch):
    client, ch_client = make_client(monkeypatch, flag="1", key="x")
    BASE = ch_client.BASE
    respx.get(f"{BASE}/search/companies").respond(json={"items": []}, headers={"ETag": "s1"})
    r = client.post("/api/companies/search", json={"q": "ACME"})
    assert r.status_code == 200
    assert r.json()["items"] == []
