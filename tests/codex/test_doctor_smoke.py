import json
import subprocess
import sys


def test_doctor_generates_report(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()

    # стабільний мок-режим для діагностики
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")

    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    rc = subprocess.call(cmd)
    assert rc == 0

    data = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))

    # базові секції
    assert "backend" in data and "rules" in data and "env" in data

    # інвентар ендпоінтів
    eps = {(e.get("method"), e.get("path")) for e in data["backend"].get("endpoints", [])}
    assert ("POST", "/api/analyze") in eps

    # summary по rules/registry
    assert data["rules"]["python"]["count"] >= 8
    assert len(data["rules"]["python"]["samples"]) <= 8

    # quality gates (ruff+mypy)
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
