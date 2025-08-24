from __future__ import annotations

import textwrap

from contract_review_app.intake.extractor import extract_clauses_flexible

SAMPLE_CONTRACT = textwrap.dedent(
    """
    DEFINITIONS
    In this Agreement, “Fees” shall mean the charges payable by the Client to the Supplier.

    TERM AND TERMINATION
    The initial term shall commence on the Effective Date. This Agreement may be terminated for material breach upon written notice of 30 days.

    PAYMENT
    The payment shall be due within 30 days of the invoice date. Late payment may incur interest.

    GOVERNING LAW AND JURISDICTION
    This Agreement shall be governed by the laws of England and Wales and the parties submit to the exclusive jurisdiction of its courts.

    CONFIDENTIALITY
    Each party agrees to keep all confidential information in strict confidence.
"""
).strip()


def test_extractor_returns_expected_clause_keys_and_texts():
    out = extract_clauses_flexible(
        SAMPLE_CONTRACT,
        min_block_len=40,
        sentence_split_over=400,
        min_match_score=0.5,
    )

    # Маємо знайти щонайменше ці 4 ключові клаузули (залежить від вашого config.CLAUSE_KEYWORDS)
    expected = {"definitions", "termination", "payment", "governing_law"}
    assert expected <= set(out.keys())

    # Перевірки, що тексти не порожні й містять реперні слова
    assert "Fees" in out["definitions"] or "fees" in out["definitions"].lower()
    assert (
        "terminated" in out["termination"].lower()
        or "terminate" in out["termination"].lower()
    )
    assert "payment" in out["payment"].lower()
    assert (
        "laws of england" in out["governing_law"].lower()
        or "governed by the laws" in out["governing_law"].lower()
    )


def test_extractor_stable_and_deterministic():
    # Двічі проганяємо — маємо отримати однаковий результат
    out1 = extract_clauses_flexible(
        SAMPLE_CONTRACT, min_block_len=40, sentence_split_over=400, min_match_score=0.5
    )
    out2 = extract_clauses_flexible(
        SAMPLE_CONTRACT, min_block_len=40, sentence_split_over=400, min_match_score=0.5
    )
    assert out1 == out2
