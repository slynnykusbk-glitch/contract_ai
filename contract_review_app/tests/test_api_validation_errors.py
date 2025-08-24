import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def test_suggest_in_xor_missing_both_returns_422():
    r = client.post("/api/suggest_edits", data=json.dumps({"text": "abc"}))
    # FastAPI+pydantic should reject body with 422
    assert r.status_code in (400, 422)

def test_qa_recheck_requires_text_non_empty():
    r = client.post("/api/qa-recheck", data=json.dumps({
        "text": "   ",
        "applied_changes": []
    }))
    assert r.status_code in (400, 422)

def test_analyze_requires_text_non_empty():
    r = client.post("/api/analyze", data=json.dumps({"text": "  "}))
    assert r.status_code in (400, 422)
