from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_suggest_edits_endpoint():
    payload = {
        "text": "Sample NDA text...",
        "findings": [
            {"code": "GLAW", "message": "something", "span": {"start": 0, "length": 6}}
        ],
    }
    resp = client.post("/api/suggest_edits", json=payload)
    assert resp.status_code == 200
    assert resp.headers.get("x-schema-version") == "1.3"
    data = resp.json()
    suggestions = data.get("suggestions")
    assert isinstance(suggestions, list) and len(suggestions) >= 1
    for s in suggestions:
        assert s["span"]["length"] > 0
        assert s["rationale"] and isinstance(s["rationale"], str)
        assert len(s.get("citations", [])) >= 1
