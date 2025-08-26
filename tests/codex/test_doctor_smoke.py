import json
import os
import subprocess
import sys
import pytest


def _run_doctor(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    rc = subprocess.call(cmd)
    assert rc == 0
    return json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))


def test_doctor_generates_report(tmp_path, monkeypatch):
    data = _run_doctor(tmp_path, monkeypatch)
    assert "backend" in data and "rules" in data and "env" in data
    eps = {(e.get("method"), e.get("path")) for e in data["backend"].get("endpoints", [])}
    assert ("POST", "/api/analyze") in eps
    assert data["rules"]["python"]["count"] >= 8


def test_smoke_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCTOR_RUN_SMOKE", raising=False)
    data = _run_doctor(tmp_path, monkeypatch)
    smoke = data["smoke"]
    assert smoke["enabled"] is False
    assert smoke["passed"] == 0
    assert smoke["failed"] == 0
    assert smoke["skipped"] == 0


@pytest.mark.skipif(os.getenv("DOCTOR_SMOKE_ACTIVE") == "1", reason="avoid recursion")
def test_smoke_enabled_runs_tests(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCTOR_RUN_SMOKE", "1")
    data = _run_doctor(tmp_path, monkeypatch)
    smoke = data["smoke"]
    assert smoke["enabled"] is True
    assert smoke["failed"] == 0
    assert smoke["passed"] > 0
