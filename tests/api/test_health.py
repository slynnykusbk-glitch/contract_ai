from fastapi.testclient import TestClient
from contract_review_app.api.app import app

def test_health_ok():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
