from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def _headers():
    return {"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION}


def test_core_selftest_e2e():
    client = TestClient(app)
    r_h = client.get("/health", headers=_headers())
    assert r_h.status_code == 200

    r_an = client.post("/api/analyze", json={"text": "Hello"}, headers=_headers())
    assert r_an.status_code == 200
    cid = r_an.headers.get("x-cid")
    assert cid

    assert client.get(f"/api/trace/{cid}.html", headers=_headers()).status_code == 200
    assert client.get(f"/api/report/{cid}.html", headers=_headers()).status_code == 200
    assert client.post("/api/summary", json={"cid": cid}, headers=_headers()).status_code == 200
    assert client.get("/api/summary", headers=_headers()).status_code == 200

    assert client.post("/api/gpt-draft", json={"text": "Example clause."}, headers=_headers()).status_code == 200
    assert (
        client.post(
            "/api/suggest_edits", json={"text": "Hi", "findings": []}, headers=_headers()
        ).status_code
        == 200
    )
