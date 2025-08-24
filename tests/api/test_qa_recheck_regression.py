from fastapi.testclient import TestClient
from contract_review_app.api.app import app

def test_qa_recheck_no_exception():
    c = TestClient(app)
    r = c.post("/api/qa-recheck", json={})
    assert r.status_code == 200
