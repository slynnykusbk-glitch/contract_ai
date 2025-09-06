from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_health_schema():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("schema") == "1.3"
    assert isinstance(data.get("rules_count"), int) and data["rules_count"] >= 1
