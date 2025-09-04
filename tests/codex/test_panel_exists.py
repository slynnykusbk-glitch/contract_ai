from starlette.testclient import TestClient

from contract_review_app.api.app import app


def _client():
    return TestClient(app, base_url="http://testserver")


def test_health_ok():
    r = _client().get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "OK"


def test_panel_assets_served():
    c = _client()
    r1 = c.get("/panel/app/assets/api-client.js")
    r2 = c.get("/panel/app/assets/store.js")
    assert r1.status_code == 200 and len(r1.text) > 50
    assert r2.status_code == 200 and len(r2.text) > 10
