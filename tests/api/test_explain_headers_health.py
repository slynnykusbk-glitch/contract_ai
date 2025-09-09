from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def test_explain_headers_and_health():
    req = {
        "finding": {
            "code": "uk_ucta_2_1_invalid",
            "message": "Exclusion of liability for personal injury",
            "span": {"start": 0, "end": 10},
        },
        "text": "Exclusion of liability for personal injury is void.",
    }
    resp = client.post("/api/explain", json=req)
    assert resp.status_code == 200
    assert "x-cid" in resp.headers
    assert resp.headers["x-schema-version"] == SCHEMA_VERSION

    health = client.get("/health")
    data = health.json()
    assert "/api/explain" in data.get("endpoints", [])
    assert data.get("schema") == SCHEMA_VERSION
