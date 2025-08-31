from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_citation_resolve_passthrough():
    payload = {"citation": {"instrument": "UK GDPR", "section": "Article 28(3)"}}
    r = client.post("/api/citation/resolve", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["citation"]["instrument"] == "UK GDPR"
    assert data["citation"]["section"] == "Article 28(3)"


def test_citation_resolve_bad_payload():
    r = client.post("/api/citation/resolve", json={})
    assert r.status_code == 400


def test_citation_resolve_unresolvable():
    payload = {"finding": {"code": "NO_SUCH_RULE", "message": "irrelevant"}}
    r = client.post("/api/citation/resolve", json=payload)
    assert r.status_code == 422
