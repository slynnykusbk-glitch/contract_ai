from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def test_gpt_draft_api_endpoint_returns_valid_response():
    input_data = {
        "text": "The parties agree to keep all information confidential.",
        "mode": "friendly",
    }

    response = client.post("/api/gpt-draft", json=input_data)

    assert response.status_code == 200
    result = response.json()

    assert result["status"] == "ok"
    assert result["mode"] == "friendly"
    assert result["proposed_text"]
    assert result["x_schema_version"] == SCHEMA_VERSION
