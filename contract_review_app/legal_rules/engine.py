"""Rule matching engine with sentence/subclause anchoring and aggregation."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Dict, Any

# deterministic ordering for severities
_SEV_ORD = {
    "critical": 3,
    "major": 2,
    "high": 2,
    "medium": 1,
    "minor": 1,
    "low": 0,
    "info": 0,
}


def _sev_ord(v: Any) -> int:
    return _SEV_ORD.get(str(v or "").lower(), 0)


def _norm_snippet(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


# ---------------------------------------------------------------------------
# Block splitting
# ---------------------------------------------------------------------------

_SENTENCE_RE = re.compile(r"[^.?!;]+[.?!;]|[^.?!;]+$", re.MULTILINE)
_SUBCLAUSE_RE = re.compile(
    r"^\s*(?:\(?\d+[\).]|[a-z][\).]|i{1,5}[\).]?)\s+", re.IGNORECASE
)


@dataclass
class Block:
    type: str
    start: int
    end: int
    text: str
    nth: int


def split_into_blocks(text: str) -> List[Block]:
    """Split text into sentence/subclause blocks with offsets."""

    blocks: List[Block] = []
    nth = {"sentence": 0, "subclause": 0}
    pos = 0
    for line in text.splitlines(True):  # keep newlines
        line_txt = line.rstrip("\n")
        line_start = pos
        line_end = line_start + len(line_txt)
        pos += len(line)
        if not line_txt:
            continue
        if _SUBCLAUSE_RE.match(line_txt):
            nth["subclause"] += 1
            blocks.append(Block("subclause", line_start, line_end, line_txt, nth["subclause"]))
            continue
        for m in _SENTENCE_RE.finditer(line_txt):
            sent = m.group(0).strip()
            if not sent:
                continue
            start = line_start + m.start()
            end = start + len(sent)
            nth["sentence"] += 1
            blocks.append(Block("sentence", start, end, sent, nth["sentence"]))
    return blocks


# ---------------------------------------------------------------------------
# Matching & aggregation
# ---------------------------------------------------------------------------


def analyze(text: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Match ``text`` against ``rules`` and return aggregated findings."""

    findings: List[Dict[str, Any]] = []
    if not text:
        return findings

    blocks = split_into_blocks(text)
    for block in blocks:
        for r in rules:
            hits = 0
            for pat in r.get("patterns", []):
                hits += len(list(pat.finditer(block.text)))
            if hits:
                findings.append(
                    {
                        "rule_id": r.get("id"),
                        "clause_type": r.get("clause_type"),
                        "severity": r.get("severity"),
                        "start": block.start,
                        "end": block.end,
                        "snippet": block.text,
                        "advice": r.get("advice", ""),
                        "law_refs": r.get("law_refs", []),
                        "suggestion": r.get("suggestion"),
                        "conflict_with": r.get("conflict_with", []),
                        "ops": r.get("ops", []),
                        "scope": {"unit": block.type, "nth": block.nth},
                        "occurrences": hits,
                    }
                )
    # Stable sort: start, end, severity desc, rule_id
    findings.sort(
        key=lambda f: (
            int(f.get("start", 0)),
            int(f.get("end", 0)),
            -_sev_ord(f.get("severity")),
            str(f.get("rule_id") or ""),
        )
    )

    # Deduplicate by (rule_id, norm(snippet), start, end)
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for f in findings:
        k = (
            f.get("rule_id"),
            _norm_snippet(f.get("snippet", "")),
            int(f.get("start", 0)),
            int(f.get("end", 0)),
        )
        if k in seen:
            continue
        seen.add(k)
        deduped.append(f)

    # Remove overlapping ranges with worse priority
    result: List[Dict[str, Any]] = []
    for f in deduped:
        keep = True
        while result and int(f["start"]) < int(result[-1]["end"]):
            prev = result[-1]
            s_curr = _sev_ord(f.get("severity"))
            s_prev = _sev_ord(prev.get("severity"))
            if s_curr > s_prev:
                result.pop()
                continue
            if s_curr < s_prev:
                keep = False
                break
            span_curr = int(f["end"]) - int(f["start"])
            span_prev = int(prev["end"]) - int(prev["start"])
            if span_curr < span_prev:
                result.pop()
                continue
            if span_curr > span_prev:
                keep = False
                break
            # same severity and span
            if (f.get("rule_id") or "") == (prev.get("rule_id") or ""):
                keep = False
                break
            # different rule_id -> keep existing prev
            keep = False
            break
        if keep:
            result.append(f)
    return result

