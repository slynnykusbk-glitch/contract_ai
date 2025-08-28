from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, cast

from contract_review_app.intake.normalization import normalize_text
from contract_review_app.intake.langseg import segment_lang_script


@dataclass(frozen=True)
class ParsedDocument:
    content: str
    normalized_text: str
    offset_map: List[int]
    segments: List[Dict[str, object]]

    @classmethod
    def from_text(cls, raw: str) -> "ParsedDocument":
        if raw is None:
            raw = ""
        norm, omap = normalize_text(raw)
        segs = segment_lang_script(norm)
        doc = cls(content=raw, normalized_text=norm, offset_map=omap, segments=segs)
        doc._assert_invariants()
        return doc

    def map_norm_to_raw(self, i: int) -> Optional[int]:
        if 0 <= i < len(self.offset_map):
            return self.offset_map[i]
        return None

    def map_norm_span_to_raw(self, start: int, end: int) -> Optional[Tuple[int, int]]:
        if start < 0 or end < 0 or start > end or end > len(self.offset_map):
            return None
        if start == end:
            return None
        start_raw = self.offset_map[start]
        end_raw = self.offset_map[end - 1] + 1
        start_raw = max(0, min(start_raw, len(self.content)))
        end_raw = max(0, min(end_raw, len(self.content)))
        if start_raw > end_raw:
            return None
        return (start_raw, end_raw)

    def _assert_invariants(self) -> None:
        om = self.offset_map
        nt = self.normalized_text
        assert len(om) == len(nt), "offset_map length must equal normalized_text length"
        prev = -1
        n_raw = len(self.content)
        for j, r in enumerate(om):
            assert 0 <= r < n_raw, f"raw index out of bounds at normalized {j}: {r}"
            assert r >= prev, f"offset_map must be non-decreasing at {j}: {r} < {prev}"
            prev = r
        if len(nt) == 0:
            assert self.segments == [] or all(
                s.get("start", 0) == 0 and s.get("end", 0) == 0 for s in self.segments
            ), "empty text must yield empty segments"
        else:
            assert (
                len(self.segments) >= 1
            ), "non-empty normalized_text must have at least 1 segment"
            cur = 0
            for s in self.segments:
                a = cast(int, s["start"])
                b = cast(int, s["end"])
                assert (
                    a == cur
                ), f"segments must be contiguous; expected start {cur}, got {a}"
                assert (
                    0 <= a < b <= len(nt)
                ), f"segment bounds invalid: {a}, {b}, len={len(nt)}"
                cur = b
            assert cur == len(
                nt
            ), f"segments must cover the full normalized_text; ended at {cur}"
