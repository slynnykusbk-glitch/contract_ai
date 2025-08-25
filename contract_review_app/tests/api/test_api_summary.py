from fastapi.testclient import TestClient

from contract_review_app.api.app import app, SCHEMA_VERSION

client = TestClient(app)


def test_summary_endpoint(monkeypatch):
    def _fake_run_analyze(inp):
        findings = [{"code": f"C{i}", "message": "risk", "severity": "critical"} for i in range(8)]
        return {
            "analysis": {"status": "WARN"},
            "results": {"general": {"status": "WARN", "findings": findings}},
            "clauses": [],
            "document": {"text": inp.text},
        }

    import contract_review_app.api.app as app_mod

    monkeypatch.setattr(app_mod, "run_analyze", _fake_run_analyze, raising=True)

    text = "Agreement [PLACEHOLDER]."
    resp = client.post("/api/summary", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["score"] > 70
    assert "M" in data["missing_exhibits"]
    assert data["placeholders"] >= 1
    assert resp.headers.get("x-schema-version") == SCHEMA_VERSION
