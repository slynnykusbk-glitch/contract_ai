from __future__ import annotations

import difflib
from typing import Tuple


def make_diff(before: str, after: str) -> Tuple[str, str]:
    """Return unified and HTML diffs for the given texts.

    The unified diff uses :func:`difflib.unified_diff` and the HTML diff uses
    :class:`difflib.HtmlDiff` without relying on any external libraries.
    """
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    unified = "\n".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    html = difflib.HtmlDiff().make_table(before_lines, after_lines)
    return unified, html
