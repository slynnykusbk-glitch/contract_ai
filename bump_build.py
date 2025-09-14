from __future__ import annotations

"""Utility for bumping cache-buster build token.

This script generates a build token of the form ``build-YYYYMMDD-HHMMSS`` and
injects it into static assets that contain the ``__BUILD_TS__`` placeholder.  The
current token is also written to ``contract_review_app/contract_review_app/static/panel/.build-token``
so that other tooling can reference the most recent build identifier.

The implementation is intentionally lightweight – it only performs a plain text
replacement and skips files that cannot be decoded as UTF-8.  It is suitable for
both manual execution and invocation from tests.
"""

from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence
import re

ROOT = Path(__file__).resolve().parent
TOKEN_FILE_REL = Path("contract_review_app/contract_review_app/static/panel/.build-token")
PLACEHOLDER = "__BUILD_TS__"
TOKEN_PATTERN = re.compile(r"build-\d{8}-\d{6}|__BUILD_TS__")


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    """Yield files under provided paths."""
    for base in paths:
        if base.is_file():
            yield base
        elif base.is_dir():
            for path in base.rglob("*"):
                if path.is_file():
                    yield path


def bump_build(root: Path | None = None, paths: Sequence[Path] | None = None) -> str:
    """Generate a new build token and inject it into static files.

    Parameters
    ----------
    root:
        Optional repository root.  Defaults to the directory containing this
        module.
    paths:
        Optional explicit paths to scan for the placeholder.  When provided,
        only these paths are searched.

    Returns
    -------
    str
        The generated build token.
    """

    repo = root or ROOT
    token = datetime.utcnow().strftime("build-%Y%m%d-%H%M%S")

    targets = list(paths) if paths is not None else [
        repo / "word_addin_dev",
        repo / "contract_review_app" / "contract_review_app" / "static" / "panel",
    ]
    for path in _iter_files(targets):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if TOKEN_PATTERN.search(text):
            path.write_text(TOKEN_PATTERN.sub(token, text), encoding="utf-8")

    token_file = (root or ROOT) / TOKEN_FILE_REL
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token, encoding="utf-8")

    return token


if __name__ == "__main__":
    bump_build()
