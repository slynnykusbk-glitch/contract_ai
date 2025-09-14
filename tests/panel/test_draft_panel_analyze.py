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


def test_draft_panel_analyze_ok():
    resp = client.post(
        "/api/analyze?clause_type=nda",
        json={"text": "Hello"},
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert "analysis" in resp.json()
