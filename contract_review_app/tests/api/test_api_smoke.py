# contract_review_app/tests/api/test_api_smoke.py
from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_api_analyze_smoke(monkeypatch):
    # Стаб аналізатора
    def _fake_analyze(text: str):
        return {"status": "OK", "findings": [], "summary": {"len": len(text)}}

    import contract_review_app.api.app as app_mod

    monkeypatch.setattr(app_mod, "_analyze_document", _fake_analyze, raising=True)

    resp = client.post("/api/analyze", json={"text": "Hello", "language": "en"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"].upper() == "OK"
    assert data["analysis"]["summary"]["len"] == 5
