import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_cli_exit_codes():
    good = subprocess.run(
        [sys.executable, "cli.py", "check", str(FIXTURES / "good_master_excerpt.txt")]
    )
    bad = subprocess.run(
        [sys.executable, "cli.py", "check", str(FIXTURES / "bad_missing_ai.txt")]
    )
    assert good.returncode == 0
    assert bad.returncode == 2
