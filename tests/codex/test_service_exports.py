import json, subprocess, sys


def _run_doctor(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    assert subprocess.call(cmd) == 0
    return json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))


def test_exceptions_available_both_places():
    from contract_review_app.gpt.interfaces import ProviderTimeoutError as A
    from contract_review_app.gpt.service import ProviderTimeoutError as B

    assert A is B


def test_doctor_reports_service_exports(tmp_path, monkeypatch):
    data = _run_doctor(tmp_path, monkeypatch)
    exports = data["service"]["exports"]
    assert exports["LLMService"]
    assert exports["load_llm_config"]
    assert exports["ProviderTimeoutError"]
    assert exports["ProviderConfigError"]
