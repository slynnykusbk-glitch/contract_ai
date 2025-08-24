from __future__ import annotations

from contract_review_app.intake.matcher import match_blocks_to_clauses, MatchCandidate


def _mk_blocks():
    return [
        "DEFINITIONS\nIn this Agreement, “Fees” shall mean the charges payable.",
        "PAYMENT TERMS\nThe payment shall be due within 30 days of the invoice date.",
        "TERM AND TERMINATION\nThis Agreement may be terminated for material breach upon notice.",
        "GOVERNING LAW\nThis Agreement shall be governed by the laws of England and Wales.",
        "Boilerplate text with no relevant words.",
    ]


def test_match_basic_scoring_and_sort_order():
    blocks = _mk_blocks()
    keywords = {
        "definitions": ["definitions", "shall mean", "means"],
        "payment": ["payment", "fees", "invoice"],
        "termination": ["terminate", "termination", "material breach", "notice"],
        "governing_law": ["governing law", "laws of england", "jurisdiction"],
    }

    out = match_blocks_to_clauses(blocks, keywords, aliases={}, min_score=0.5)

    # Має бути принаймні по одному кандидату для кожної з 4 клаузул
    clause_types = {c.clause_type for c in out}
    assert {"definitions", "payment", "termination", "governing_law"} <= clause_types

    # Найперші 1–2 кандидати мають відповідати сильним збігам (із заголовком)
    top = out[0]
    assert isinstance(top, MatchCandidate)
    assert top.block_index in (0, 1, 2, 3)
    assert top.score >= 1.0

    # Перевіримо, що блок без ключових слів не створює кандидатів
    assert all(c.block_index != 4 for c in out)


def test_heading_bonus_affects_score_order():
    blocks = [
        "TERMINATION\nNotice and material breach shall entitle a party to terminate.",
        "The payment is due on invoice date.",
    ]
    keywords = {
        "termination": ["terminate", "termination", "notice", "material breach"],
        "payment": ["payment", "invoice"],
    }
    out = match_blocks_to_clauses(blocks, keywords, aliases={}, min_score=0.1)

    # Перша позиція — скоріше за все termination через заголовок
    assert out[0].clause_type == "termination"
    assert out[0].block_index == 0
    # payment також має бути знайдена у другому блоці
    assert any(c.clause_type == "payment" and c.block_index == 1 for c in out)


def test_position_bonus_prefers_earlier_blocks_when_equal_tf():
    blocks = [
        "Payment shall be made within 30 days.",
        "Payment shall be made within 30 days.",
    ]
    keywords = {"payment": ["payment"]}
    out = match_blocks_to_clauses(blocks, keywords, aliases={}, min_score=0.1)

    # Оскільки TF однаковий, перший блок має мати >= бал через позиційний бонус
    first = [c for c in out if c.clause_type == "payment" and c.block_index == 0][0]
    second = [c for c in out if c.clause_type == "payment" and c.block_index == 1][0]
    assert first.score >= second.score


def test_min_score_filters_noise():
    blocks = ["Some unrelated text.", "Another block without matches."]
    keywords = {"payment": ["invoice"]}
    out = match_blocks_to_clauses(blocks, keywords, aliases={}, min_score=0.9)
    assert out == []
