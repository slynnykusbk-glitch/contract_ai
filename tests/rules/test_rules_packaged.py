from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import subprocess


def test_rules_packaged(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist), "."],
        check=True,
    )
    wheel = next(dist.glob("*.whl"))
    with zipfile.ZipFile(wheel) as zf:
        files = [
            n for n in zf.namelist() if n.endswith(".yaml") and "policy_packs" in n
        ]
    assert files, "YAML rule packs missing in wheel"
