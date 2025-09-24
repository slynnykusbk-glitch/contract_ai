from fastapi.testclient import TestClient

from contract_review_app.api.app import TRACE


TEXT = """
This Agreement shall be governed by the laws of England and Wales.

The parties submit to the exclusive jurisdiction of the courts of France.
"""


def _call_analyze(client: TestClient) -> tuple[dict, str]:
    response = client.post("/api/analyze", json={"text": TEXT})
    assert response.status_code == 200
    return response.json(), response.headers.get("x-cid", "")


def test_l2_constraints_toggle(monkeypatch):
    from contract_review_app.api import app as app_module

    monkeypatch.setattr(app_module, "FEATURE_LX_ENGINE", True, raising=False)
    monkeypatch.setattr(app_module, "LX_L2_CONSTRAINTS", False, raising=False)

    client = TestClient(app_module.app)
    client.headers.update(
        {"x-api-key": "test", "x-schema-version": app_module.SCHEMA_VERSION}
    )

    baseline_payload, baseline_cid = _call_analyze(client)
    assert baseline_cid
    baseline_findings = baseline_payload["analysis"]["findings"]
    assert all(
        not str(f.get("rule_id", "")).startswith("L2::") for f in baseline_findings
    )

    baseline_trace = TRACE.get(baseline_cid)
    assert baseline_trace is not None
    baseline_constraints = (baseline_trace.get("body") or {}).get("constraints")
    if baseline_constraints is not None:
        assert isinstance(baseline_constraints, dict)
        assert baseline_constraints.get("checks") == []

    app_module.an_cache._data.clear()
    app_module.IDEMPOTENCY_CACHE._data.clear()
    app_module.cid_index._data.clear()

    monkeypatch.setattr(app_module, "LX_L2_CONSTRAINTS", True, raising=False)

    enhanced_payload, enhanced_cid = _call_analyze(client)
    assert enhanced_cid
    enhanced_findings = enhanced_payload["analysis"]["findings"]

    non_l2_baseline = [
        f for f in baseline_findings if not str(f.get("rule_id", "")).startswith("L2::")
    ]
    non_l2_enhanced = [
        f for f in enhanced_findings if not str(f.get("rule_id", "")).startswith("L2::")
    ]
    assert non_l2_enhanced == non_l2_baseline

    l2_findings = [
        f for f in enhanced_findings if str(f.get("rule_id", "")).startswith("L2::")
    ]
    assert l2_findings, "L2 findings should appear when the flag is enabled"
    assert any(f.get("rule_id") == "L2::L2-010" for f in l2_findings)

    trace_entry = TRACE.get(enhanced_cid)
    assert trace_entry is not None
    constraints_payload = (trace_entry.get("body") or {}).get("constraints")
    assert isinstance(constraints_payload, dict)
    checks = constraints_payload.get("checks") or []
    assert checks, "expected constraint checks in trace payload"
    assert all(
        (check.get("result") in {"pass", "fail", "skip"})
        for check in checks
        if isinstance(check, dict)
    )
    assert any(
        isinstance(check, dict)
        and check.get("result") == "fail"
        and isinstance(check.get("details"), dict)
        and check["details"].get("rule_id") == "L2::L2-010"
        for check in checks
    )
