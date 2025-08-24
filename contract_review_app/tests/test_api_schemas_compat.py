import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.core.schemas import AnalyzeOut, DraftOut, SuggestOut, QARecheckOut

client = TestClient(app)

def test_analyze_response_is_compatible_with_AnalyzeOut():
    r = client.post("/api/analyze", data=json.dumps({"text": "A short clause."}))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    # Build AnalyzeOut from envelope fields
    payload = {
        "analysis": j["analysis"],
        "results": j.get("results", {}),
        "clauses": j.get("clauses", []),
        "document": j["document"],
        "schema_version": j.get("schema_version", "1.0"),
    }
    # Will raise if incompatible:
    _ = AnalyzeOut(**payload)

def test_draft_response_is_compatible_with_DraftOut():
    r = client.post("/api/gpt/draft", data=json.dumps({"text": "Make this clause polite."}))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    payload = {k: j[k] for k in ("draft_text",) if k in j}
    payload["alternatives"] = j.get("alternatives", [])
    payload["rationale"] = j.get("rationale")
    payload["citations_hint"] = j.get("citations_hint", [])
    payload["model"] = j.get("model", "rule-based")
    payload["elapsed_ms"] = j.get("elapsed_ms")
    payload["metadata"] = j.get("metadata", {})
    _ = DraftOut(**payload)

def test_suggest_response_is_compatible_with_SuggestOut():
    r = client.post("/api/suggest_edits", data=json.dumps({
        "text": "Warranty lasts 12 months.",
        "clause_type": "warranty",
        "mode": "friendly",
        "top_k": 1
    }))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    payload = {"suggestions": j.get("suggestions", []), "model": j.get("model", "rule-based"),
               "elapsed_ms": j.get("elapsed_ms"), "metadata": j.get("metadata", {})}
    _ = SuggestOut(**payload)

def test_qarecheck_response_is_compatible_with_QARecheckOut():
    r = client.post("/api/qa-recheck", data=json.dumps({
        "text": "NDA applies to disclosures.",
        "applied_changes": [{"range": {"start": 0, "length": 3}, "text": "The NDA"}]
    }))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    payload = {k: j[k] for k in ("score_delta", "risk_delta", "status_from", "status_to", "residual_risks") if k in j}
    _ = QARecheckOut(**payload)
