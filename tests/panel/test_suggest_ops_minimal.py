import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def _apply_ops(text: str, ops):
    result = text
    for op in sorted(ops, key=lambda o: o["start"], reverse=True):
        result = result[: op["start"]] + op["replacement"] + result[op["end"] :]
    return result


def test_suggest_edits_ops_patch():
    original = "bad clause"
    r = client.post("/api/suggest_edits", json={"text": original})
    assert r.status_code == 200
    data = r.json()
    proposed = data.get("proposed_text", "")
    ops = data.get("ops", [])
    assert isinstance(ops, list)
    if proposed and proposed != original:
        assert ops, "ops should describe edits"
        patched = _apply_ops(original, ops)
        assert patched == proposed
