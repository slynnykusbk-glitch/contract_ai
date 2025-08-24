from fastapi.testclient import TestClient
from contract_review_app.api.app import app

def test_health():
    c = TestClient(app)
    r = c.get('/health')
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'