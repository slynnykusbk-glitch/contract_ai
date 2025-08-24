import json

from fastapi.testclient import TestClient

from contract_review_app.api.app import app


client = TestClient(app)


def test_health_rules_count_positive():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("rules_count", 0) > 0


def test_analyze_finds_governing_law():
    text = "This agreement is governed by the laws of England and Wales."
    r = client.post("/api/analyze", data=json.dumps({"text": text}))
    assert r.status_code == 200
    findings = r.json().get("analysis", {}).get("findings", [])
    assert any(f.get("clause_type") == "governing_law" for f in findings)

