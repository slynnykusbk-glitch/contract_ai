"""Text normalization utilities with offset mapping."""

REPLACEMENTS = {
    "“": '"',
    "”": '"',
    "«": '"',
    "»": '"',
    "‚": '"',
    "‘": '"',
    "’": '"',
    "–": "-",
    "—": "-",
    "−": "-",
    "\u00a0": " ",
    "\u202f": " ",
}


def normalize_with_offsets(s: str) -> tuple[str, list[int]]:
    """Normalize text and record the index of each original character."""

    normalized_chars: list[str] = []
    offsets: list[int] = []

    for idx, ch in enumerate(s):
        normalized_chars.append(REPLACEMENTS.get(ch, ch))
        offsets.append(idx)

    return "".join(normalized_chars), offsets
