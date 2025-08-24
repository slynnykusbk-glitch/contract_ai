from __future__ import annotations

from typing import Dict, List

from contract_review_app.intake.text_cleaning import preprocess_text
from contract_review_app.intake.splitter import split_into_candidate_blocks
from contract_review_app.intake.patterns import load_clause_patterns
from contract_review_app.intake.matcher import match_blocks_to_clauses, MatchCandidate
from contract_review_app.intake.resolver import resolve_conflicts, ResolvedClause
from contract_review_app.intake.loader import load_docx_text


def extract_clauses_flexible(
    raw_text: str,
    *,
    min_block_len: int = 60,
    sentence_split_over: int = 800,
    min_match_score: float = 0.5,
) -> Dict[str, str]:
    """
    K7: Повний конвеєр витягання клаузул з «будь-якого» сирого тексту контракту.

    Кроки:
      1) Preprocess (K1) → очищення тексту.
      2) Split (K2) → абзаци/підблоки/речення → список blocks[List[str]].
      3) Patterns (K4) → завантаження ключових слів і alias-ів.
      4) Match (K5) → скоринг блоків проти патернів → кандидати.
      5) Resolve (K6) → 1 найкращий блок на кожний clause_type.
      6) Build result → {clause_type: full_block_text}.

    Повертає:
      Dict[str, str] де ключ — canonical clause_type (lowercase), значення — повний текст обраного блока.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        return {}

    # 1) preprocess
    clean = preprocess_text(raw_text)

    # 2) split → blocks
    blocks = split_into_candidate_blocks(
        clean, min_len=min_block_len, sentence_split_over=sentence_split_over
    )
    if not blocks:
        return {}

    # 3) patterns (keywords + aliases). aliases наразі не потрібні на матчинг, але тримаємо на майбутнє
    keywords, aliases = load_clause_patterns()

    # 4) match
    candidates: List[MatchCandidate] = match_blocks_to_clauses(
        blocks, keywords, aliases, min_score=min_match_score
    )

    # 5) resolve
    resolved: List[ResolvedClause] = resolve_conflicts(candidates)

    # 6) build {clause_type: text}
    out: Dict[str, str] = {}
    for r in resolved:
        if 0 <= r.block_index < len(blocks):
            out[r.clause_type] = blocks[r.block_index].strip()

    return out


def extract_from_docx(
    path: str,
    *,
    min_block_len: int = 60,
    sentence_split_over: int = 800,
    min_match_score: float = 0.5,
) -> Dict[str, str]:
    """
    Зручна обгортка: читає .docx → викликає extract_clauses_flexible().
    Якщо файл не читається — повертає {}.
    """
    text = load_docx_text(path)
    if not text:
        return {}
    return extract_clauses_flexible(
        text,
        min_block_len=min_block_len,
        sentence_split_over=sentence_split_over,
        min_match_score=min_match_score,
    )
