from __future__ import annotations

from typing import Any, Dict, List, Literal

Status = Literal["verified", "partially_verified", "unverified", "failed"]


def verify_output_contains_citations(
    result_text: str, evidence: List[Dict[str, Any]]
) -> Status:
    """
    Heuristic: 'verified' if all evidence ids like [c1],[c2] appear; 'partially_verified' if some;
    'unverified' if none. 'failed' only if result_text empty.
    """
    if not (result_text or "").strip():
        return "failed"
    ids = [str(e.get("id") or "").strip() for e in evidence if e.get("id")]
    if not ids:
        return "unverified"
    found = 0
    for cid in ids:
        marker = f"[{cid}]"
        if marker in result_text:
            found += 1
    if found == len(ids):
        return "verified"
    if found == 0:
        return "unverified"
    return "partially_verified"
