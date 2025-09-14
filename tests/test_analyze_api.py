import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")

client = TestClient(app)


def _headers():
    return {"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION}


def test_analyze_flat_ok():
    resp = client.post("/api/analyze", json={"text": "Hello", "mode": "live"}, headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["schema_version"] == SCHEMA_VERSION
    assert "analysis" in data and isinstance(data["analysis"], dict)
    assert "findings" in data and isinstance(data["findings"], list)
    assert "recommendations" in data and isinstance(data["recommendations"], list)


def test_analyze_wrapped_ok():
    resp = client.post(
        "/api/analyze",
        json={"payload": {"text": "Hello", "mode": "live"}},
        headers=_headers(),
    )
    assert resp.status_code == 200


def test_analyze_bad_422():
    resp = client.post("/api/analyze", json={"mode": "live"}, headers=_headers())
    assert resp.status_code == 422
    detail = resp.json().get("detail")
    assert isinstance(detail, list) and detail
    loc = detail[0].get("loc")
    assert loc and tuple(loc)[0] == "text"
