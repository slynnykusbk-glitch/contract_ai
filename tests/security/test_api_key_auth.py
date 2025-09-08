import importlib
from fastapi.testclient import TestClient


def _get_client(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "secret")
    import contract_review_app.api.app as app_module
    importlib.reload(app_module)
    return TestClient(app_module.app)


def test_api_key_auth(monkeypatch):
    client = _get_client(monkeypatch)
    payload = {"text": "Hello"}

    r = client.post("/api/analyze", json=payload)
    assert r.status_code == 401
    r = client.post("/api/gpt-draft", json={"text": "Ping", "mode": "friendly"})
    assert r.status_code == 401
    r = client.post("/api/suggest_edits", json=payload)
    assert r.status_code == 401

    headers = {"x-api-key": "secret", "x-schema-version": "1.3"}
    assert client.post("/api/analyze", json=payload, headers=headers).status_code == 200
    assert (
        client.post(
            "/api/gpt-draft",
            json={"text": "Ping", "mode": "friendly"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post("/api/suggest_edits", json=payload, headers=headers).status_code
        == 200
    )
