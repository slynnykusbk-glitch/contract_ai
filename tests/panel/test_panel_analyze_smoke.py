import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def _headers():
    return {
        "x-api-key": os.getenv("API_KEY", "local-test-key-123"),
        "x-schema-version": SCHEMA_VERSION,
    }


def test_panel_analyze_returns_flat_json():
    resp = client.post(
        "/api/analyze", json={"text": "Hello", "mode": "live"}, headers=_headers()
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "payload" not in data
    assert isinstance(data.get("analysis"), dict)
    assert isinstance(data["analysis"].get("findings"), list)
