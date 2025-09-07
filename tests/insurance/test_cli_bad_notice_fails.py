import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_cli_bad_notice_fails():
    path = FIXTURES / "bad_notice_14.txt"
    proc = subprocess.run([sys.executable, "cli.py", "check", str(path)], capture_output=True, text=True)
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    entry = next(r for r in data["hard"] if r["key"] == "cancel_notice_days")
    assert entry["status"] == "FAIL"
