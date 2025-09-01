import pytest
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def test_gpt_draft_api_endpoint_returns_valid_response():
    payload = {
        "text": "The parties agree to keep all information confidential.",
        "mode": "friendly",
    }

    response = client.post("/api/gpt-draft", json=payload)
    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "ok"
    assert result["mode"] == payload["mode"]
    assert result["before_text"] == payload["text"]
    assert result["after_text"]
    assert result["diff"]["type"] == "unified"
    assert result["x_schema_version"] == SCHEMA_VERSION
