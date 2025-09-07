from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)

REQ = {
    "finding": {
        "code": "uk_ucta_2_1_invalid",
        "message": "Exclusion of liability for personal injury",
        "span": {"start": 0, "end": 10},
    },
    "text": "Exclusion of liability for personal injury is void.",
}


def test_api_key_required(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "secret")
    resp = client.post("/api/explain", json=REQ)
    assert resp.status_code == 401
    resp2 = client.post("/api/explain", headers={"x-api-key": "secret"}, json=REQ)
    assert resp2.status_code == 200
