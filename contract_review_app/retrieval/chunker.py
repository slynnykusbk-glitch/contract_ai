from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import blake2b
from typing import List, Optional


@dataclass
class ChunkDTO:
    text: str
    start: int
    end: int
    lang: Optional[str] = None
    token_count: int = 0
    checksum: str = ""


def _normalise_text(s: str) -> str:
    lines = [line.strip() for line in s.splitlines()]
    return "\n".join(lines).strip()


def _token_count(s: str) -> int:
    return len(re.findall(r"\w+", s))


def chunk_text(
    text: str,
    *,
    lang: str | None = None,
    max_chars: int = 800,
    overlap: int = 120,
    stride: int | None = None,
) -> List[ChunkDTO]:
    """Deterministically chunk ``text`` into overlapping pieces."""

    if stride is None:
        stride = max_chars - overlap
    chunks: List[ChunkDTO] = []

    # split by paragraphs (blank lines)
    parts = []
    pos = 0
    for m in re.finditer(r"\n\s*\n+", text):
        parts.append((pos, m.start()))
        pos = m.end()
    parts.append((pos, len(text)))

    for p_start, p_end in parts:
        block = text[p_start:p_end]
        if not block:
            continue
        start = 0
        while start < len(block):
            end = min(start + max_chars, len(block))
            if end < len(block):
                # try to cut at sentence or newline boundary
                boundary = max(
                    block.rfind(".", start, end),
                    block.rfind("!", start, end),
                    block.rfind("?", start, end),
                    block.rfind("\n", start, end),
                )
                if boundary > start:
                    end = boundary + 1
            piece = block[start:end]
            abs_start = p_start + start
            abs_end = p_start + end
            norm = _normalise_text(piece)
            checksum = blake2b(norm.encode("utf-8"), digest_size=16).hexdigest()
            tokens = _token_count(piece)
            chunks.append(
                ChunkDTO(
                    text=piece,
                    start=abs_start,
                    end=abs_end,
                    lang=lang,
                    token_count=tokens,
                    checksum=checksum,
                )
            )
            if end == len(block):
                break
            start = end - overlap
    return chunks
