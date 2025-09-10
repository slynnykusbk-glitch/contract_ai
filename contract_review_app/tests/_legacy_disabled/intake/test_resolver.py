from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
from contract_review_app.intake.resolver import resolve_conflicts


@dataclass(frozen=True)
class MC:
    clause_type: str
    block_index: int
    score: float
    matched_terms: Tuple[str, ...]
    text_preview: str = ""


def test_resolve_picks_best_by_score_then_position_then_terms():
    cands = [
        MC("payment", 5, 2.0, ("payment",)),
        MC(
            "payment", 2, 2.0, ("payment", "invoice")
        ),  # такий самий score, але раніше і більше термів
        MC("payment", 10, 1.9, ("invoice",)),
        MC("termination", 3, 1.1, ("notice",)),
        MC(
            "termination", 2, 1.1, ("notice", "terminate")
        ),  # такий самий score, але раніше і більше термів
    ]
    out = resolve_conflicts(cands)
    # Має бути по 1 на кожний clause_type
    assert {r.clause_type for r in out} == {"payment", "termination"}

    # Для payment — другий кандидат (block 2) кращий за рахунок позиції та кількості термів
    p = next(r for r in out if r.clause_type == "payment")
    assert p.block_index == 2 and p.score == 2.0

    # Для termination — block 2 кращий за той самий бал, але раніший та з більшою кількістю термів
    t = next(r for r in out if r.clause_type == "termination")
    assert t.block_index == 2 and t.score == 1.1


def test_resolve_ignores_invalid_items_and_stable_order():
    # Некоректні записи мають ігноруватися
    class Bad:
        pass

    cands = [
        Bad(),
        MC("governing_law", 1, 0.9, ("laws of england",)),
        MC("definitions", 0, 1.5, ("definitions",)),
    ]
    out = resolve_conflicts(cands)
    # Відсортовано стабільно за clause_type
    assert [r.clause_type for r in out] == ["definitions", "governing_law"]
