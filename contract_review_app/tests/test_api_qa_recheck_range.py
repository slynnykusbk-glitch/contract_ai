import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def _env_headers():
    return {"x-cid": "test-cid-qa-range"}

def test_qa_recheck_accepts_range_and_span():
    text = "Hello world!"
    # 1) range{start,length}
    body1 = {
        "text": text,
        "applied_changes": [
            {"range": {"start": 6, "length": 5}, "replacement": "LAWYER"}
        ]
    }
    r1 = client.post("/api/qa-recheck", data=json.dumps(body1), headers=_env_headers())
    assert r1.status_code == 200
    j1 = r1.json()
    # Плоскі дельти є, типи коректні
    assert j1["status"] == "ok"
    for k in ("risk_delta","score_delta"):
        assert isinstance(j1[k], int)
    assert "status_from" in j1 and "status_to" in j1
    assert isinstance(j1.get("residual_risks", []), list)

    # 2) span{start,end}
    body2 = {
        "text": text,
        "applied_changes": [
            {"span": {"start": 6, "end": 11}, "text": "LEGAL"}
        ]
    }
    r2 = client.post("/api/qa-recheck", data=json.dumps(body2), headers=_env_headers())
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["status"] == "ok"

def test_suggest_edits_returns_range_norm():
    # мінімальний кейс: fallback path також нормалізує range
    body = {
        "text": "Payment shall be made promptly upon invoice.",
        "clause_id": "payment-1",
        "mode": "friendly",
        "top_k": 1
    }
    r = client.post("/api/suggest_edits", data=json.dumps(body))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert isinstance(j["suggestions"], list) and len(j["suggestions"]) >= 1
    sug = j["suggestions"][0]
    assert "range" in sug and "start" in sug["range"] and "length" in sug["range"]
