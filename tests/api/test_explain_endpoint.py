from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def test_explain_basic():
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
    assert resp.headers["x-schema-version"] == SCHEMA_VERSION
    data = resp.json()
    assert data["x_schema_version"] == SCHEMA_VERSION
    assert data["reasoning"]
    assert data["trace"]
    assert any("UCTA" in c.get("instrument", "") for c in data["citations"])
    assert any("2(1)" in c.get("section", "") for c in data["citations"])
    assert data["verification_status"] in {"ok", "missing_citations"}
