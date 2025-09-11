import os
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ.setdefault("AZURE_OPENAI_API_KEY", "test")
os.environ.setdefault("SCHEMA_VERSION", "1.4")
from contract_review_app.api.app import app
from contract_review_app.intake.normalization import normalize_for_intake

client = TestClient(app)


def test_analyze_returns_normalized_snippet():
    text = "Process\u00a0Agent\r\nfoo"
    fake = {"rule_id": "r1", "severity": "high", "snippet": text}
    with (
        patch("contract_review_app.legal_rules.loader.load_rule_packs"),
        patch("contract_review_app.legal_rules.loader.filter_rules", return_value=[]),
        patch("contract_review_app.legal_rules.engine.analyze", return_value=[fake]),
    ):
        resp = client.post(
            "/api/analyze", json={"text": text}, headers={"x-schema-version": "1.4"}
        )
    assert resp.status_code == 200
    data = resp.json()
    findings = (
        data.get("findings")
        or data.get("analysis", {}).get("findings")
        or data.get("results", {}).get("analysis", {}).get("findings", [])
        or []
    )
    assert findings
    f = findings[0]
    assert f["normalized_snippet"] == normalize_for_intake(f["snippet"])
