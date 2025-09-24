from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})


def test_api_analyze_returns_type():
    text = (
        "NON-DISCLOSURE AGREEMENT\n"
        "Confidential Information shall be returned or destroyed by the Receiving Party after the Permitted Purpose."
    )
    resp = client.post("/api/analyze", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    summary = data.get("summary", {})
    assert isinstance(summary.get("type"), str)
    assert summary.get("doc_type", {}).get("source") in {
        "title",
        "keywords",
        "classifier",
    }
    rc = data.get("rules_coverage", {})
    assert rc.get("doc_type", {}).get("value") == summary.get("type")
    assert any(r.get("status") == "doc_type_mismatch" for r in rc.get("rules", []))
