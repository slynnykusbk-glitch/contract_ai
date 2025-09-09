import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_gpt_draft_payload_and_response():
    r_an = client.post("/api/analyze", json={"text": "Ping"})
    cid = r_an.headers.get("x-cid")
    payload = {"cid": cid, "clause": "Ping", "mode": "friendly"}
    r = client.post("/api/gpt-draft", json=payload)
    assert r.status_code == 200
    data = r.json()
    for k in ("cid", "clause", "mode"):
        assert k in payload and isinstance(payload[k], str)
    assert isinstance(data.get("proposed_text"), str)
    assert data["proposed_text"].strip() != ""
