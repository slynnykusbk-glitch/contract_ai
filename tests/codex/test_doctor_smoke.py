import json
import os
import subprocess
import sys
import pytest


def _run_doctor(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()

    # стабільний мок-режим для діагностики
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")

    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    rc = subprocess.call(cmd)
    assert rc == 0
    return json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))


def test_doctor_generates_report(tmp_path, monkeypatch):
    data = _run_doctor(tmp_path, monkeypatch)

    # базові секції
    assert "backend" in data and "rules" in data and "env" in data

    # інвентар ендпоінтів
    eps = {(e.get("method"), e.get("path")) for e in data["backend"].get("endpoints", [])}
    assert ("POST", "/api/analyze") in eps

    # summary по rules/registry
    assert data["rules"]["python"]["count"] >= 8
    assert len(data["rules"]["python"]["samples"]) <= 8

    # quality gates (ruff/mypy)
    quality = data.get("quality", {})
    assert quality.get("ruff", {}).get("status") == "ok"
    assert isinstance(quality.get("ruff", {}).get("issues_total"), int)
    assert quality.get("mypy", {}).get("status") in {"ok", "skipped"}

    # runtime self-checks бекенда
    checks = data.get("runtime_checks", {})
    assert checks.get("health", {}).get("status") == 200
    assert checks.get("openapi", {}).get("status") == 200

    # інваріанти по env
    for key in ["provider", "model", "timeout_s", "node_is_mock"]:
        assert key in data["env"], f"missing LLM {key}"


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
    # вмикаємо smoke-режим виконання частини тестів усередині doctor
    monkeypatch.setenv("DOCTOR_RUN_SMOKE", "1")
    data = _run_doctor(tmp_path, monkeypatch)
    smoke = data["smoke"]
    assert smoke["enabled"] is True
    assert smoke["failed"] == 0
    assert smoke["passed"] > 0
