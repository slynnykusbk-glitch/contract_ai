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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import re

ROOT = Path(__file__).resolve().parent
TOKEN_FILE_REL = Path("contract_review_app/contract_review_app/static/panel/.build-token")
PLACEHOLDER = "__BUILD_TS__"
TOKEN_PATTERN = re.compile(r"build-\d{8}-\d{6}|__BUILD_TS__")
TASKPANE_BUNDLE_PATTERN = re.compile(
    r"((?:\./)?taskpane\.bundle\.js)(?:\?b=(?:build-\d{8}-\d{6}|__BUILD_TS__))?"
)
PANEL_TASKPANE_PATTERN = re.compile(
    r"((?:https?://[^\s\"']+)?/panel/taskpane\.html(?:\?[^\s\"']*)?)"
)


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    """Yield files under provided paths."""
    for base in paths:
        if base.is_file():
            yield base
        elif base.is_dir():
            for path in base.rglob("*"):
                if path.is_file():
                    yield path


def _ensure_query_param(url: str, key: str, token: str) -> str:
    """Attach or update a query parameter with the current build token."""

    parsed = urlsplit(url)
    pairs = [
        (name, value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
        if name != key
    ]
    pairs.append((key, token))
    new_query = urlencode(pairs, doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


def inject_cache_busters(text: str, token: str) -> str:
    """Inject cache-busting query parameters into panel assets."""

    updated = TOKEN_PATTERN.sub(token, text)

    if "taskpane.bundle.js" in updated:
        updated = TASKPANE_BUNDLE_PATTERN.sub(
            lambda match: f"{match.group(1)}?b={token}", updated
        )

    if "/panel/taskpane.html" in updated:
        def _replace_url(match: re.Match) -> str:
            url = match.group(1)
            url = _ensure_query_param(url, "b", token)
            url = _ensure_query_param(url, "v", token)
            return url

        updated = PANEL_TASKPANE_PATTERN.sub(_replace_url, updated)

    return updated


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
        if TOKEN_PATTERN.search(text) or "taskpane.bundle.js" in text or "/panel/taskpane.html" in text:
            path.write_text(inject_cache_busters(text, token), encoding="utf-8")

    token_file = (root or ROOT) / TOKEN_FILE_REL
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token, encoding="utf-8")

    return token


if __name__ == "__main__":
    bump_build()
