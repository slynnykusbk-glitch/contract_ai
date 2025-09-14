"""Build script for panel static assets.

This script is intended to be invoked from ``npm run build:panel``.  It bumps
the build token (replacing ``__BUILD_TS__`` placeholders) and then copies the
panel artefacts from ``word_addin_dev`` into
``contract_review_app/contract_review_app/static/panel``.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import shutil
import sys
import subprocess

# Ensure project root on sys.path so direct invocation works
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(ROOT.as_posix())

from bump_build import bump_build

SRC = ROOT / "word_addin_dev"
DEST = ROOT / "contract_review_app" / "contract_review_app" / "static" / "panel"
ASSETS_SRC = SRC / "app" / "assets"

FILES = [
    "taskpane.html",
    "taskpane.bundle.js",
]


def main(*, run_tests: bool = False) -> None:
    """Build panel assets and optionally run vitest."""
    if run_tests:
        # run vitest suite to ensure DOM contract before copying assets
        subprocess.run(
            [
                "npm",
                "--prefix",
                "word_addin_dev",
                "ci",
            ],
            check=True,
            cwd=ROOT,
        )
        subprocess.run(
            [
                "npm",
                "--prefix",
                "word_addin_dev",
                "run",
                "test",
            ],
            check=True,
            cwd=ROOT,
        )

    token = bump_build(paths=[DEST])

    DEST.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dst = DEST / name
        shutil.copy2(SRC / name, dst)
        try:
            text = dst.read_text(encoding="utf-8")
            dst.write_text(text.replace("__BUILD_TS__", token), encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            pass

    # copy auxiliary assets referenced from taskpane.html
    assets_dest = DEST / "app" / "assets"
    shutil.copytree(ASSETS_SRC, assets_dest, dirs_exist_ok=True)
    for path in assets_dest.rglob("*"):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        path.write_text(text.replace("__BUILD_TS__", token), encoding="utf-8")

    (DEST / ".build-token").write_text(token, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="run npm install and vitest before copying assets",
    )
    main(run_tests=parser.parse_args().run_tests)
