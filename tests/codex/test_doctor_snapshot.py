import json, subprocess, sys
from pathlib import Path


def _shape(obj):
    if isinstance(obj, dict):
        return {k: _shape(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_shape(obj[0])] if obj else []
    return type(obj).__name__


def test_doctor_sections_shape(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    rc = subprocess.call(cmd)
    assert rc == 0
    data = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))
    sections = {name: _shape(data[name]) for name in ["git", "llm", "addin", "inventory"]}
    snapshot_path = Path(__file__).with_name("doctor_sections_snapshot.json")
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert sections == expected
