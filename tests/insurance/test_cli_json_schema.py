import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_cli_json_schema():
    path = FIXTURES / "good_master_excerpt.txt"
    proc = subprocess.run(
        [sys.executable, "cli.py", "check", str(path)], capture_output=True, text=True
    )
    data = json.loads(proc.stdout)
    assert set(data.keys()) == {"extract", "hard", "soft", "summary"}
