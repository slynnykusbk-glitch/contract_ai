from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_gpt_draft_returns_text_and_headers():
    r_an = client.post("/api/analyze", json={"text": "Example clause."})
    cid = r_an.headers.get("x-cid")
    r = client.post("/api/gpt-draft", json={"cid": cid, "clause": "Example clause."})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["proposed_text"]
    for hdr in ("x-schema-version", "x-latency-ms", "x-cid"):
        assert hdr in r.headers
