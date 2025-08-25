import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def test_health_has_status_schema_and_header():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-schema-version") == "1.1"
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("schema") == "1.1"
    assert isinstance(data.get("rules_count"), int)
