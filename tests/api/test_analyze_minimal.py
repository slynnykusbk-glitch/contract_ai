from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_analyze_minimal():
    resp = client.post("/api/analyze", json={"text": "Hello", "language": "en"})
    assert resp.status_code == 200
    assert resp.headers["x-schema-version"] == "1.3"
    data = resp.json()
    assert isinstance(data.get("analysis"), dict) and data["analysis"]
