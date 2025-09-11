from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)

REQ = {
    "finding": {
        "code": "uk_ucta_2_1_invalid",
        "message": "Exclusion of liability for personal injury",
        "span": {"start": 0, "end": 10},
    },
    "text": "Exclusion of liability for personal injury is void.",
}


def test_api_key_required():
    resp = client.post("/api/explain", json=REQ)
    assert resp.status_code == 401
    resp2 = client.post(
        "/api/explain",
        headers={"x-api-key": "secret", "x-schema-version": SCHEMA_VERSION},
        json=REQ,
    )
    assert resp2.status_code == 200
