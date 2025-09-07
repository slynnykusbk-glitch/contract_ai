from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_panel_redlines_returns_diffs():
    payload = {"before_text": "hello world", "after_text": "hello there"}
    r = client.post("/api/panel/redlines", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    diff_u = data.get("diff_unified", "")
    diff_h = data.get("diff_html", "")
    assert diff_u and diff_h
    lines = diff_u.splitlines()
    assert lines[0].startswith("--- ")
    assert lines[1].startswith("+++ ")
    assert any(l.startswith("@@") for l in lines)
