import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run_doctor(tmp_path):
    prefix = tmp_path / "diag" / "analysis"
    prefix.parent.mkdir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["LLM_PROVIDER"] = "mock"
    env["LLM_MODEL"] = "mock"
    env["LLM_TIMEOUT"] = "5"
    env["DOCTOR_SMOKE"] = "0"
    cmd = [sys.executable, "tools/doctor.py", "--out", str(prefix), "--json"]
    rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
    assert rc == 0
    data = json.loads(prefix.with_suffix(".json").read_text(encoding="utf-8"))
    return data


@pytest.mark.skipif(os.getenv("DOCTOR_SMOKE_ACTIVE") == "1", reason="avoid recursion")
def test_env_has_llm_keys_and_smoke_runs(tmp_path):
    d = _run_doctor(tmp_path)

    # LLM ключі продубльовані в env (бек-компат з існуючими тестами)
    for k in ("provider", "model", "timeout_s", "node_is_mock"):
        assert k in d["env"], f"missing {k} in env"
    assert d["env"]["provider"] == "mock"
    assert d["env"]["model"] == "mock"

    # smoke вимкнено для швидкого прогону
    smoke = d.get("smoke", {})
    assert smoke.get("enabled") is False

    # якість: ruff зібраний (будь-яке не-негативне число)
    quality = d.get("quality", {})
    ruff = quality.get("ruff", {})
    assert ruff.get("status") == "ok"
    assert isinstance(ruff.get("issues_total"), int)
    assert ruff["issues_total"] >= 0

    # runtime health перевірка
    runtime = d.get("runtime_checks", {})
    assert runtime.get("health", {}).get("status") == 200
    assert runtime.get("openapi", {}).get("status") == 200
