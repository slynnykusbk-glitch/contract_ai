from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List

RETENTION_DAYS = int(os.getenv("CR_RETENTION_DAYS", "30"))
VAR_PATH = Path(__file__).resolve().parents[2] / "var"


def purge(dry_run: bool = True) -> list[Path]:
    cutoff = time.time() - RETENTION_DAYS * 86400
    removed: list[Path] = []
    if not VAR_PATH.exists():
        return removed
    for p in VAR_PATH.glob("**/*"):
        if p.is_file() and p.stat().st_mtime < cutoff:
            removed.append(p)
            if not dry_run:
                try:
                    p.unlink()
                except Exception:
                    pass
    return removed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    for path in purge(dry_run=args.dry):
        print(path)
