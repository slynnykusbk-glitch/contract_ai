from __future__ import annotations

from typing import Dict, List


def rrf(bm25_ids: List[int], vec_ids: List[int], k: int = 60) -> List[int]:
    """Reciprocal rank fusion of id lists."""
    scores: Dict[int, float] = {}
    for rank, i in enumerate(bm25_ids, 1):
        scores[i] = scores.get(i, 0.0) + 1.0 / (k + rank)
    for rank, i in enumerate(vec_ids, 1):
        scores[i] = scores.get(i, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda x: (-scores[x], x))


def weighted_fusion(
    bm25_ids: List[int],
    vec_ids: List[int],
    w_bm25: float,
    w_vec: float,
    k: int = 60,
) -> List[int]:
    """Weighted hybrid fusion of id lists."""
    scores: Dict[int, float] = {}
    for rank, i in enumerate(bm25_ids, 1):
        scores[i] = scores.get(i, 0.0) + w_bm25 / (k + rank)
    for rank, i in enumerate(vec_ids, 1):
        scores[i] = scores.get(i, 0.0) + w_vec / (k + rank)
    return sorted(scores, key=lambda x: (-scores[x], x))
