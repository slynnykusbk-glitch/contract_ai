from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.intake.normalization import normalize_for_intake

client = TestClient(app)


def test_analyze_returns_normalized_snippet():
    text = "Process\u00A0Agent\r\nfoo"
    resp = client.post("/api/analyze", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    findings = data.get("findings") or data.get("results", {}).get("analysis", {}).get("findings", [])
    assert findings
    f = findings[0]
    assert f["normalized_snippet"] == normalize_for_intake(f["snippet"])
