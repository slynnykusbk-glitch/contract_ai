import json
import subprocess
import sys


def test_doctor_repo_hygiene(tmp_path, monkeypatch):
    prefix = tmp_path / "diag" / "analysis"
    prefix.parent.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    cmd = [sys.executable, "tools/doctor.py", "--out", str(prefix), "--json"]
    rc = subprocess.call(cmd)
    assert rc == 0
    data = json.loads(prefix.with_suffix(".json").read_text(encoding="utf-8"))
    assert "repo" in data
    repo = data["repo"]
    assert "tracked_pyc" in repo
    assert "suggestions" in repo
