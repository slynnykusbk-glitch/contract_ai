from fastapi.testclient import TestClient

import contract_review_app.api.app as app_module
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def test_trace_contains_coverage_block(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")
    monkeypatch.setenv("FEATURE_TRACE_ARTIFACTS", "1")
    monkeypatch.setenv("FEATURE_COVERAGE_MAP", "1")
    monkeypatch.setattr(app_module, "FEATURE_TRACE_ARTIFACTS", True, raising=False)
    monkeypatch.setattr(app_module, "FEATURE_COVERAGE_MAP", True, raising=False)
    client = TestClient(app)
    text = (
        "Payment Terms. Customer shall pay invoices within 30 days.\n"
        "Governing Law. English law applies.\n"
    )
    headers = {"x-api-key": "dummy", "x-schema-version": SCHEMA_VERSION}
    resp = client.post("/api/analyze", json={"text": text}, headers=headers)
    assert resp.status_code == 200
    cid = resp.headers["x-cid"]
    trace = client.get(f"/api/trace/{cid}").json()
    coverage = trace.get("coverage")
    assert coverage is not None
    assert coverage["version"] >= 1
    assert coverage["zones_total"] >= 30
    assert 0 <= coverage["zones_present"] <= coverage["zones_total"]
    assert 0 <= coverage["zones_candidates"] <= coverage["zones_total"]
    assert 0 <= coverage["zones_fired"] <= coverage["zones_total"]
    assert len(coverage.get("details", [])) <= 50
    for detail in coverage.get("details", []):
        assert "text" not in detail
        assert detail.get("segments") is not None
        assert len(detail.get("segments", [])) <= 3
        for segment in detail.get("segments", []):
            assert set(segment.keys()) <= {"index", "span"}
            assert len(segment.get("span", [])) == 2
        for key in ("candidate_rules", "fired_rules", "missing_rules"):
            assert isinstance(detail.get(key), list)
    response_payload = resp.json()
    assert "coverage" not in response_payload
