from __future__ import annotations

import re


def make_snippet(text: str, query: str, window: int = 80) -> str:
    """Return a short snippet around the first match of query tokens.

    The algorithm is deterministic:
    * tokenize ``query`` into lowercase words;
    * find the earliest occurrence of any token in ``text`` (case-insensitive);
    * return ``window`` characters of context on both sides;
    * trim to string bounds and prepend/append "…" if cut off;
    * if no token is found, return the head of ``text`` of length ``2*window``.
    """
    tokens = re.findall(r"\w+", query.lower())
    text_len = len(text)
    text_lower = text.lower()
    match_pos: int | None = None
    match_len = 0
    for tok in tokens:
        idx = text_lower.find(tok)
        if idx != -1 and (match_pos is None or idx < match_pos):
            match_pos = idx
            match_len = len(tok)
    if match_pos is not None:
        start = max(match_pos - window, 0)
        end = min(match_pos + match_len + window, text_len)
        snippet = text[start:end]
        if start > 0:
            snippet = "…" + snippet
        if end < text_len:
            snippet += "…"
        return snippet
    # Fallback: head of the text
    end = min(2 * window, text_len)
    snippet = text[:end]
    if end < text_len:
        snippet += "…"
    return snippet
