import json, subprocess, sys, pathlib


def test_doctor_generates_report(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    rc = subprocess.call(cmd)
    assert rc == 0
    data = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))
    assert "backend" in data and "rules" in data and "env" in data
    assert "llm" in data
    for key in ["provider", "model", "timeout_s", "mode_is_mock"]:
        assert key in data["llm"], f"missing llm.{key}"
    eps = {(e.get("method"), e.get("path")) for e in data["backend"].get("endpoints", [])}
    assert ("POST", "/api/analyze") in eps
    assert data["rules"]["python"]["count"] >= 8
