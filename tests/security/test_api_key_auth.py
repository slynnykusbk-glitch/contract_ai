import importlib
from fastapi.testclient import TestClient
from contract_review_app.api.models import SCHEMA_VERSION


def _get_client():
    from contract_review_app.api.app import app

    return TestClient(app)


def test_api_key_auth():
    client = _get_client()
    payload = {"text": "Hello"}

    r = client.post("/api/analyze", json=payload)
    assert r.status_code == 401
    r = client.post(
        "/api/gpt-draft", json={"cid": "x", "clause": "Ping", "mode": "friendly"}
    )
    assert r.status_code == 401
    r = client.post("/api/suggest_edits", json=payload)
    assert r.status_code == 401

    headers = {"x-api-key": "secret", "x-schema-version": SCHEMA_VERSION}
    r_an = client.post("/api/analyze", json=payload, headers=headers)
    assert r_an.status_code == 200
    cid = r_an.headers.get("X-Cid")
    assert (
        client.post(
            "/api/gpt-draft",
            json={"cid": cid, "clause": "Ping", "mode": "friendly"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post("/api/suggest_edits", json=payload, headers=headers).status_code
        == 200
    )
