import json
from fastapi.testclient import TestClient

from contract_review_app.api.app import app

client = TestClient(app)


def test_api_returns_string_replacement():
    payload = {
        "text": "This contract is governed by the laws of Mars.",
        "clause_type": "governing_law",
    }
    r = client.post("/api/suggest_edits", data=json.dumps(payload))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert isinstance(j.get("edits"), list)
    assert j["edits"], "expected edits"
    replacement = j["edits"][0]["replacement"]
    assert isinstance(replacement, str)
    assert "[object Object]" not in replacement
