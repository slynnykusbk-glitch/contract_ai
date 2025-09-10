import json
from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.core.schemas import AnalyzeOut, QARecheckOut

client = TestClient(app)


def test_analyze_response_is_compatible_with_AnalyzeOut():
    r = client.post("/api/analyze", content=json.dumps({"text": "A short clause."}))
    assert r.status_code == 200
    j = r.json()
    assert j["status"].upper() == "OK"
    # Build AnalyzeOut from envelope fields
    payload = {
        "analysis": j.get("analysis", {}),
        "results": j.get("results", {}),
        "clauses": j.get("clauses", []),
        "document": j.get("document", {}),
        "schema_version": j.get("schema_version", "1.0"),
    }
    for f in payload["analysis"].get("findings", []):
        f.setdefault("code", "")
        f.setdefault("message", f.get("text", ""))
    _ = AnalyzeOut(**payload)


def test_suggest_response_shape():
    r = client.post(
        "/api/suggest_edits", content=json.dumps({"text": "Warranty lasts 12 months."})
    )
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert isinstance(j.get("proposed_text"), str)


def test_qarecheck_response_is_compatible_with_QARecheckOut():
    r = client.post(
        "/api/qa-recheck",
        content=json.dumps(
            {
                "text": "NDA applies to disclosures.",
                "applied_changes": [
                    {"range": {"start": 0, "length": 3}, "text": "The NDA"}
                ],
            }
        ),
    )
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    payload = {
        k: j[k]
        for k in (
            "score_delta",
            "risk_delta",
            "status_from",
            "status_to",
            "residual_risks",
        )
        if k in j
    }
    _ = QARecheckOut(**payload)
