from pathlib import Path

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "soft_mixed_warns.txt"


def test_trace_meta_risk_threshold_and_anchor():
    client, modules = _build_client("1")
    try:
        text = FIXTURE_PATH.read_text(encoding="utf-8")
        response = client.post("/api/analyze", headers=_headers(), json={"text": text})
        assert response.status_code == 200

        cid = response.headers.get("x-cid")
        assert cid

        from contract_review_app.api import app as app_module

        trace_entry = app_module.TRACE.get(cid)
        assert trace_entry is not None

        trace_meta = trace_entry.get("meta") or {}
        assert trace_meta.get("risk_threshold") in {"low", "medium", "high", "critical"}

        body = trace_entry.get("body") or {}
        analysis = body.get("analysis") or {}
        findings = analysis.get("findings") or []
        assert findings, "expected findings in trace payload"

        anchor = findings[0].get("anchor")
        assert isinstance(anchor, dict)
        assert anchor.get("method") in {"nth", "token", "text"}
    finally:
        _cleanup(client, modules)
