from pathlib import Path
from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_analyze_engine_pipeline_returns_findings():
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "nda_mini.txt"
    text = fixture.read_text(encoding="utf-8")
    r = client.post("/api/analyze", json={"text": text})
    assert r.status_code == 200
    findings = r.json()["analysis"]["findings"]
    assert len(findings) >= 6
