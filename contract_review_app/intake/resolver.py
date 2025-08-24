from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class ResolvedClause:
    clause_type: str  # canonical, lowercase
    block_index: int  # індекс обраного блока
    score: float  # фінальний бал
    matched_terms: Tuple[str, ...]
    text_preview: str


def resolve_conflicts(candidates: Iterable) -> List[ResolvedClause]:
    """
    Приймає Iterable MatchCandidate (із matcher.match_blocks_to_clauses)
    та повертає по 1 кращому кандидату на кожний clause_type.

    Тай-брейки (строго детерміновано):
      1) score ↓ (більший — кращий)
      2) block_index ↑ (раніший у документі — кращий)
      3) len(matched_terms) ↓ (більше збігів — кращий; отже мінус для сортування)
      4) clause_type ↑ (алфавіт — стабілізатор)
    """
    by_clause: Dict[str, List] = {}
    for c in candidates or []:
        # Захист від «неправильних» об’єктів
        if not hasattr(c, "clause_type") or not hasattr(c, "score"):
            continue
        ct = str(getattr(c, "clause_type", "") or "").strip().lower()
        if not ct:
            continue
        by_clause.setdefault(ct, []).append(c)

    resolved: List[ResolvedClause] = []
    for ct, lst in by_clause.items():
        # Сортуємо за компаратором і беремо перший
        lst.sort(
            key=lambda x: (
                -float(getattr(x, "score", 0.0)),
                int(getattr(x, "block_index", 10**9)),
                -len(tuple(getattr(x, "matched_terms", ()) or ())),
                str(getattr(x, "clause_type", "") or ""),
            )
        )
        best = lst[0]
        resolved.append(
            ResolvedClause(
                clause_type=ct,
                block_index=int(getattr(best, "block_index", -1)),
                score=float(getattr(best, "score", 0.0)),
                matched_terms=tuple(getattr(best, "matched_terms", ()) or ()),
                text_preview=str(getattr(best, "text_preview", "") or ""),
            )
        )

    # Повертаємо у стабільному порядку за назвою клаузули
    resolved.sort(key=lambda r: r.clause_type)
    return resolved
