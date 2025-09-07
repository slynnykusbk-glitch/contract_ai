import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_cli_good_all_green():
    path = FIXTURES / "good_master_excerpt.txt"
    proc = subprocess.run([sys.executable, "cli.py", "check", str(path)], capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["summary"]["hard_fail_count"] == 0
