import json
import subprocess
import sys

from fastapi.testclient import TestClient

from contract_review_app.api.models import SCHEMA_VERSION


def _run_doctor(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    assert subprocess.call(cmd) == 0
    return json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))


def test_app_has_analyze_hook(monkeypatch):
    import contract_review_app.api.app as app_mod

    assert hasattr(app_mod, "_analyze_document")

    def fake(text: str):
        return {"status": "OK", "findings": [{"id": "X"}], "summary": {"len": len(text)}}

    monkeypatch.setattr(app_mod, "_analyze_document", fake, raising=True)

    # перевіримо, що ендпоїнт існує у маршрутах
    from contract_review_app.api.app import app

    assert any(getattr(r, "path", None) == "/api/analyze" for r in app.routes)


def test_doctor_reports_analyze_hook(tmp_path, monkeypatch):
    data = _run_doctor(tmp_path, monkeypatch)
    assert data["api"]["has__analyze_document"] is True


def test_analyze_lx_engine_trace(monkeypatch):
    import contract_review_app.api.app as app_module

    monkeypatch.setenv("FEATURE_LX_ENGINE", "1")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("AZURE_KEY_INVALID", "0")
    monkeypatch.setattr(app_module, "FEATURE_LX_ENGINE", True, raising=False)

    with TestClient(app_module.app) as client:
        resp = client.post(
            "/api/analyze",
            json={"text": "Hello LX"},
            headers={
                "x-schema-version": SCHEMA_VERSION,
                "x-api-key": "local-test-key-123",
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload.get("schema_version") == SCHEMA_VERSION
        cid = resp.headers.get("x-cid")
        assert cid

        trace_resp = client.get(
            f"/api/trace/{cid}",
            headers={"x-schema-version": SCHEMA_VERSION},
        )
        assert trace_resp.status_code == 200
        trace_body = trace_resp.json()
        assert trace_body.get("l0_features", {}).get("status") == "enabled"
        assert "count" in trace_body.get("l0_features", {})
