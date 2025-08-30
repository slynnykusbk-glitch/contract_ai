import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def apply_suggestion(text: str, suggestion: dict) -> str:
    insert = suggestion.get("proposed_text") or suggestion.get("message", "")
    start = suggestion.get("range", {}).get("start", 0)
    length = suggestion.get("range", {}).get("length", 0)
    return text[:start] + insert + text[start + length:]

def test_suggest_edits_apply_governing_law():
    original = "This Agreement shall be governed by the laws of Mars."
    payload = {"text": original, "clause_type": "governing_law", "mode": "friendly", "top_k": 1}
    r = client.post("/api/suggest_edits", content=json.dumps(payload))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data.get("suggestions"), "No suggestions returned"
    suggestion = data["suggestions"][0]
    updated = apply_suggestion(original, suggestion)
    assert isinstance(updated, str) and len(updated) >= len(original)
