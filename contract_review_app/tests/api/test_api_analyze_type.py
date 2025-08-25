from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_api_analyze_returns_type():
    text = (
        "NON-DISCLOSURE AGREEMENT\n"
        "Confidential Information shall be returned or destroyed by the Receiving Party after the Permitted Purpose."
    )
    resp = client.post("/api/analyze", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]["summary"]["type"] == "NDA"
    assert data["results"]["summary"]["type_confidence"] >= 0.6
