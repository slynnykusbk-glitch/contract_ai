from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_citation_resolve_passthrough():
    payload = {"citations": [{"instrument": "UK GDPR", "section": "Article 28(3)"}]}
    r = client.post("/api/citation/resolve", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["citations"][0]["instrument"] == "UK GDPR"
    assert data["citations"][0]["section"] == "Article 28(3)"


def test_citation_resolve_bad_payload():
    r = client.post("/api/citation/resolve", json={})
    assert r.status_code == 400


def test_citation_resolve_unresolvable():
    payload = {
        "findings": [
            {"span": {"start": 0, "end": 1}, "text": "irrelevant", "lang": "latin"}
        ]
    }
    r = client.post("/api/citation/resolve", json=payload)
    assert r.status_code == 422
