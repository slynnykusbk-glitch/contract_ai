from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


client = TestClient(app)


def _h():
    return {"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION}


def test_analyze_contract_ok():
    resp = client.post("/api/analyze", json={"text": "Sample"}, headers=_h())
    assert resp.status_code == 200
    assert resp.headers.get("x-schema-version") == SCHEMA_VERSION
    assert resp.headers.get("x-cid")
    data = resp.json()
    assert data["schema_version"] == SCHEMA_VERSION
    assert data.get("cid")
    assert "clause_type" in data.get("summary", {})
    assert isinstance(data.get("findings"), list)
    assert isinstance(data.get("recommendations"), list)


def test_analyze_contract_empty_text():
    resp = client.post("/api/analyze", json={"text": ""}, headers=_h())
    assert resp.status_code == 422
    data = resp.json()
    assert isinstance(data.get("detail"), list)
    assert any("loc" in d and "msg" in d for d in data["detail"])
