import json
import pytest
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


@pytest.mark.parametrize("extra", [{}, {"schema": "1.4"}])
def test_gpt_draft_payload_and_response(extra):
    r_an = client.post(
        "/api/analyze",
        json={"mode": "live", "text": "Ping"},
        headers={"x-api-key": "k", "x-schema-version": "1.4"},
    )
    cid = r_an.headers.get("x-cid")
    payload = {"clause_id": cid, "text": "Ping", "mode": "friendly"}
    payload.update(extra)
    r = client.post(
        "/api/gpt-draft",
        json=payload,
        headers={"x-api-key": "k", "x-schema-version": "1.4"},
    )
    assert r.status_code == 200
    data = r.json()
    for k in ("clause_id", "text", "mode"):
        assert k in payload and isinstance(payload[k], str)
    assert isinstance(data.get("draft_text"), str)
    assert data["draft_text"].strip() != ""
