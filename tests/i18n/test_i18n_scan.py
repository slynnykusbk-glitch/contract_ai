import subprocess
import sys
from pathlib import Path


def run_scan(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/i18n_scan.py", str(target)],
        capture_output=True,
        text=True,
    )


def test_detects_cyrillic(tmp_path: Path):
    p = tmp_path / "bad.txt"
    p.write_text("hello\nпривет")
    proc = run_scan(tmp_path)
    assert proc.returncode == 1
    assert "bad.txt" in proc.stdout


def test_scan_is_deterministic(tmp_path: Path):
    p = tmp_path / "bad.txt"
    p.write_text("привет")
    first = run_scan(tmp_path)
    second = run_scan(tmp_path)
    assert first.stdout == second.stdout
