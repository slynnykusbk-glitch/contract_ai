from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_ok_findings_only():
    payload = {"findings": [{"message": "gdpr"}]}
    r = client.post("/api/citation/resolve", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["citations"], "expected citations returned"


def test_ok_citations_only():
    payload = {"citations": [{"instrument": "Act", "section": "1"}]}
    r = client.post("/api/citation/resolve", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["citations"][0]["instrument"] == "Act"


def test_fail_both_or_none_400():
    both = {
        "findings": [{"message": "gdpr"}],
        "citations": [{"instrument": "Act", "section": "1"}],
    }
    r1 = client.post("/api/citation/resolve", json=both)
    r2 = client.post("/api/citation/resolve", json={})
    assert r1.status_code == 400
    assert r2.status_code == 400
