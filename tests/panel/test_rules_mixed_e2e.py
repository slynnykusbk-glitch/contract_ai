import json
from pathlib import Path

from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION
from contract_review_app.engine.report_html import render_html_report


def test_rules_mixed_e2e(tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    client = TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})

    text = Path("fixtures/contracts/mixed_sample.txt").read_text(encoding="utf-8")
    resp = client.post("/api/analyze?debug=coverage", json={"text": text})
    assert resp.status_code == 200

    data = resp.json()
    fired = sorted({r["rule_id"] for r in data["meta"]["fired_rules"]})
    assert len(fired) >= 8

    snap_path = Path(__file__).with_name("test_rules_mixed_e2e_snapshot.json")
    expected = json.loads(snap_path.read_text(encoding="utf-8"))
    assert fired == expected

    trace = data
    trace["cid"] = resp.headers.get("x-cid", "")
    report_html = render_html_report(trace)
    (tmp_path / "mixed_sample_report.html").write_text(report_html, encoding="utf-8")
