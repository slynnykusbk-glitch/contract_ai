"""Build script for panel static assets.

This script is intended to be invoked from ``npm run build:panel``.  It bumps
the build token (replacing ``__BUILD_TS__`` placeholders) and then copies the
panel artefacts from ``word_addin_dev`` into
``contract_review_app/contract_review_app/static/panel``.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from bump_build import bump_build

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "word_addin_dev"
DEST = ROOT / "contract_review_app" / "contract_review_app" / "static" / "panel"

FILES = [
    "taskpane.html",
    "taskpane.bundle.js",
    "panel_selftest.html",
]


def main() -> None:
    bump_build(ROOT)

    DEST.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copy2(SRC / name, DEST / name)

    # Copy assets directory
    shutil.copytree(SRC / "app" / "assets", DEST / "app" / "assets", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
