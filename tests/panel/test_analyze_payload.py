 from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def _headers():
    return {"x-api-key": "k", "x-schema-version": "1.4"}

def test_analyze_flat_body_ok():
    r = client.post("/api/analyze",
                    json={"schema": "1.4", "text": "Ping", "mode": "live"},
                    headers=_headers())
    assert r.status_code == 200

def test_analyze_payload_wrapper_ok():
    r = client.post("/api/analyze",
                    json={"payload": {"schema": "1.4", "text": "Ping", "mode": "live"}},
                    headers=_headers())
    assert r.status_code == 200

def test_analyze_bad_422_with_details():
    r = client.post("/api/analyze",
                    json={"text": 123},
                    headers=_headers())
    assert r.status_code == 422
    j = r.json()
    assert isinstance(j.get("detail"), list)
    assert any(("loc" in d and "msg" in d) for d in j["detail"])
