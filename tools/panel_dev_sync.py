"""Synchronize panel assets for development.

This helper builds the Word add-in and copies fresh artefacts into the
server's static panel directory.  It ensures that the developer panel and
the backend serve identical assets by delegating to ``build_panel`` which
handles copying and cache busting.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from tools import build_panel

ROOT = Path(__file__).resolve().parents[1]


def build_ts() -> None:
    """Compile TypeScript sources to JavaScript using npm."""
    subprocess.run(
        ["npm", "--prefix", "word_addin_dev", "run", "build"],
        check=True,
        cwd=ROOT,
    )


def main() -> None:
    build_ts()
    build_panel.main()


if __name__ == "__main__":
    main()
