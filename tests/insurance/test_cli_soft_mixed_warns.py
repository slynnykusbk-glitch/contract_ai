import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_cli_soft_mixed_warns():
    path = FIXTURES / "soft_mixed_warns.txt"
    proc = subprocess.run([sys.executable, "cli.py", "check", str(path)], capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["summary"]["hard_fail_count"] == 0
    assert data["summary"]["soft_warn_count"] >= 1
