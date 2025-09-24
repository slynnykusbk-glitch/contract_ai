"""CI guard against accidental loopback host references."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_no_loopback_strings() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pattern = ("local" + "host") + r"(:[0-9]+)?"
    cmd = [
        "git",
        "grep",
        "-n",
        "-I",
        "-E",
        pattern,
        "--",
        ".",
        ":(exclude)docs/**",
        ":(exclude)_deprecated/**",
    ]
    result = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True)
    if result.returncode == 0:
        sample = "\n".join(result.stdout.splitlines()[:20])
        raise AssertionError(f"Found forbidden loopback reference(s):\n{sample}")
    assert result.returncode == 1, result.stderr
