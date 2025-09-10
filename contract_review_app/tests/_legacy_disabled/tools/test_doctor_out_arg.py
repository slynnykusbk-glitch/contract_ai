import json
import sys
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def run_doctor(out_arg: str, *flags):
    cmd = [sys.executable, str(ROOT / "tools" / "doctor.py"), "--out", out_arg, *flags]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def test_legacy_dir_mode(tmp_path):
    outdir = tmp_path / "out"
    outdir.mkdir()
    cp = run_doctor(str(outdir), "--json")
    assert cp.returncode == 0, cp.stderr
    f = outdir / "analysis.json"
    assert f.is_file()
    data = json.loads(f.read_text(encoding="utf-8"))
    assert "blocks" in data and len(data["blocks"]) == 14
    assert (outdir / "state.log").exists()


def test_prefix_mode(tmp_path):
    prefix = tmp_path / "diag"
    cp = run_doctor(str(prefix), "--json")
    assert cp.returncode == 0, cp.stderr
    f = prefix.with_suffix(".json")
    assert f.is_file()
    data = json.loads(f.read_text(encoding="utf-8"))
    assert "generated_at_utc" in data
    assert (prefix.parent / "state.log").exists()

