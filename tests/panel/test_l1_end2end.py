import importlib
from pathlib import Path

from fastapi.testclient import TestClient

import contract_review_app.api.app as app_module


def test_l1_end_to_end_dispatch(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    original_flag = "1" if getattr(app_module, "FEATURE_LX_ENGINE", False) else "0"

    try:
        monkeypatch.setenv("FEATURE_LX_ENGINE", "1")
        reloaded = importlib.reload(app_module)

        with TestClient(
            reloaded.app,
            headers={
                "x-schema-version": reloaded.SCHEMA_VERSION,
                "x-api-key": "local-test-key-123",
            },
        ) as client:
            text = Path("fixtures/contracts/mixed_sample.txt").read_text(
                encoding="utf-8"
            )
            resp = client.post("/api/analyze?debug=coverage", json={"text": text})
            assert resp.status_code == 200

            payload = resp.json()
            fired = [
                item["rule_id"]
                for item in payload.get("meta", {}).get("fired_rules", [])
            ]
            assert isinstance(fired, list)

            cid = resp.headers.get("x-cid", "")
            trace_entry = reloaded.TRACE.get(cid)
            dispatch = ((trace_entry or {}).get("body") or {}).get("dispatch")
            assert dispatch
            segments = dispatch.get("segments", [])
            assert segments
            candidate_ids = {
                cand["rule_id"]
                for seg in segments
                for cand in seg.get("candidates", [])
            }
            assert candidate_ids
    finally:
        monkeypatch.setenv("FEATURE_LX_ENGINE", original_flag)
        importlib.reload(app_module)
