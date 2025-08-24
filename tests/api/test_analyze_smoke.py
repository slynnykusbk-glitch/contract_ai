from fastapi.testclient import TestClient
from contract_review_app.api.app import app

def test_analyze_smoke():
    c = TestClient(app)
    r = c.post("/api/analyze", json={"text": "Either party may terminate for convenience."})
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
