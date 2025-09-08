from fastapi.testclient import TestClient
from contract_review_app.api import app as app_module

client = TestClient(app_module.app)


def test_api_key_required(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "secret")

    r = client.post("/api/analyze", json={"text": "hi"})
    assert r.status_code == 401

    r = client.post(
        "/api/analyze",
        json={"text": "hi"},
        headers={"x-api-key": "secret", "x-schema-version": "1.3"},
    )
    assert r.status_code == 200
