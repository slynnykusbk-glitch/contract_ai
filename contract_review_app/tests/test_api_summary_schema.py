import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app, SCHEMA_VERSION

client = TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})

def test_summary_has_status_and_schema_version():
    payload = {"text": "This Agreement shall be governed by the laws of England and Wales."}
    r_analyze = client.post("/api/analyze", json=payload)
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    r = client.post("/api/summary", json={"cid": cid})
    assert r.status_code == 200
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION
    data = r.json()
    assert data.get("status") == "ok"
    summary = data.get("summary")
    for key in [
        "type",
        "type_confidence",
        "parties",
        "dates",
        "signatures",
        "term",
        "governing_law",
        "jurisdiction",
        "liability",
        "carveouts",
        "conditions_vs_warranties",
        "hints",
    ]:
        assert key in summary
    assert isinstance(summary["type"], str)
    assert 0.0 <= summary["type_confidence"] <= 1.0
