import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def test_summary_has_status_and_schema_version():
    payload = {"text":"This Agreement shall be governed by the laws of England and Wales."}
    r = client.post("/api/summary", json=payload)
    assert r.status_code == 200
    assert r.headers.get("x-schema-version") == "1.1"
    data = r.json()
    assert data.get("status") == "ok"
    assert "summary" in data
    assert data.get("schema_version") == "1.1"
