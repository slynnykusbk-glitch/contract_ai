import pytest
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def test_gpt_draft_api_endpoint_returns_valid_response():
    # 📝 Тестовий AnalysisOutput — як JSON
    input_data = {
        "clause_type": "Confidentiality",
        "text": "The parties agree to keep all information confidential.",
        "status": "FAIL",
        "findings": [],
        "recommendations": ["Clarify what information is considered confidential."],
        "diagnostics": {
            "rule": "confidentiality_check",
            "rule_version": "1.0"
        },
        "trace": [],
        "score": 42
    }

    response = client.post("/api/gpt-draft", json=input_data)

    assert response.status_code == 200
    result = response.json()

    # 🔍 Перевірки структури відповіді
    assert result["clause_type"] == "Confidentiality"
    assert result["text"] != input_data["text"]
    assert "confidential" in result["text"].lower()
    assert result["score"] >= input_data["score"]
    assert "explanation" in result or "recommendations" in result
