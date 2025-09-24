from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_redlines_minimal_ok():
    payload = {"before_text": "a", "after_text": "b"}
    r = client.post("/api/panel/redlines", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert isinstance(data.get("diff_unified"), str)
    assert isinstance(data.get("diff_html"), str)
