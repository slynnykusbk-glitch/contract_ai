from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable


@dataclass(frozen=True)
class MatchCandidate:
    clause_type: str  # canonical, lowercase (e.g., "termination")
    block_index: int  # індекс блока в початковому списку
    score: float  # загальний бал
    matched_terms: Tuple[str, ...]  # унікальні ключові слова/фрази, що збіглися
    text_preview: str  # короткий прев'ю (перші ~200 символів)


_HEADING_LINE_RE = re.compile(r"^[A-Z][A-Z0-9 &/\-]{2,}$")  # ALL CAPS
_NUMBERED_TITLE_RE = re.compile(r"^\s*\d+(\.\d+)*[.)]?\s+[A-Z].{0,120}$")

_WORDISH = r"[A-Za-zА-Яа-яІіЇїЄє0-9’'\-]"


def _is_heading_line(line: str) -> bool:
    line = (line or "").strip()
    if not line or len(line) > 140:
        return False
    return bool(_HEADING_LINE_RE.match(line) or _NUMBERED_TITLE_RE.match(line))


def _iter_keywords(keywords: Dict[str, List[str]]) -> Iterable[Tuple[str, str]]:
    """
    Ітеруємося по (clause_type, kw) — все очікується у lowercase.
    Порожні/не-рядкові пропускаємо.
    """
    for ctype, lst in (keywords or {}).items():
        if not isinstance(ctype, str) or not ctype.strip():
            continue
        ctype_l = ctype.strip().lower()
        for kw in lst or []:
            if isinstance(kw, str) and kw.strip():
                yield ctype_l, kw.strip().lower()


def _count_phrase_occurrences(text_lc: str, phrase_lc: str) -> int:
    """
    Рахує нечутливі до регістру входження фрази як окремих слів/послідовностей.
    - Для слів: використовує word-boundaries.
    - Для багатослівних фраз: шукає як послідовність із пробілами.
    """
    # екранізуємо спецсимволи
    esc = re.escape(phrase_lc)
    # межі для "словоподібних" символів, щоб не ловити шматки в середині слова
    pattern = rf"(?<!{_WORDISH}){esc}(?!{_WORDISH})"
    return len(re.findall(pattern, text_lc, flags=re.IGNORECASE))


def _heading_bonus(heading_text_lc: str, keywords_for_clause: List[str]) -> float:
    """
    Якщо будь-яке ключове слово зустрічається в першому рядку (який виглядає як заголовок),
    додаємо бонус.
    """
    for kw in keywords_for_clause:
        if kw in heading_text_lc:
            return 2.0  # константний бонус; можна параметризувати при потребі
    return 0.0


def _position_bonus(block_index: int, total_blocks: int) -> float:
    """
    Ранній блок у документі отримує більший бонус.
    f(i) = 0.5 * (1 - i/(N-1))  для N>1; 0 для N<=1
    """
    if total_blocks <= 1:
        return 0.0
    rel = 1.0 - (block_index / (total_blocks - 1))
    return 0.5 * max(0.0, min(1.0, rel))


def _tf_score_for_block(block_lc: str, clause_kw: List[str]) -> Tuple[float, List[str]]:
    """
    TF-скірінг: сума входжень усіх ключових фраз (мінімум 0).
    Повертає (score, matched_terms_unique).
    """
    matched: List[str] = []
    score = 0.0
    for kw in clause_kw:
        cnt = _count_phrase_occurrences(block_lc, kw)
        if cnt > 0:
            score += float(cnt)
            matched.append(kw)
    # унікалізуємо з детермінованим порядком
    matched = sorted(set(matched))
    return score, matched


def match_blocks_to_clauses(
    blocks: List[str],
    keywords: Dict[str, List[str]],
    aliases: Dict[str, str] | None = None,
    *,
    min_score: float = 0.5,
) -> List[MatchCandidate]:
    """
    Обчислює скоринг для кожного блока відносно кожної клаузули.
    Складається з:
      - TF входжень ключових фраз у блоці;
      - бонус за наявність ключового слова в заголовку (перший рядок, якщо виглядає як заголовок);
      - позиційний бонус (раніші блоки мають трохи вищий бал).

    Повертає відсортований детермінований список MatchCandidate
    (спочатку за спаданням score, далі за block_index, далі за clause_type).

    Фільтрація: кандидати з підсумковим балом < min_score відкидаються.

    Примітка: `aliases` тут не застосовуються, оскільки матчимо проти ключових слів.
    Вони будуть корисні на етапах K6/K7 для злиття альтернативних назв.
    """
    if not isinstance(blocks, list) or not blocks:
        return []

    # Підготовка lowercase блоків і заголовків
    blocks_lc = [str(b or "").strip().lower() for b in blocks]
    first_lines = [
        ((b.split("\n", 1))[0] if isinstance(b, str) else "").strip() for b in blocks
    ]
    is_heading = [_is_heading_line(fl) for fl in first_lines]
    headings_lc = [fl.lower() for fl in first_lines]

    total = len(blocks)
    out: List[MatchCandidate] = []

    # Нормалізуємо ключові слова (очікуємо, що вони вже lowercase після K4; але підстрахуємось)
    normalized_kw: Dict[str, List[str]] = {}
    for ctype, kw in keywords.items():
        if not isinstance(ctype, str) or not ctype.strip():
            continue
        lst = [
            str(k).strip().lower()
            for k in (kw or [])
            if isinstance(k, str) and k.strip()
        ]
        if lst:
            normalized_kw[ctype.strip().lower()] = sorted(set(lst))

    for idx, block in enumerate(blocks):
        block_lc = blocks_lc[idx]
        for clause_type, clause_kw in normalized_kw.items():
            tf_s, matched_terms = _tf_score_for_block(block_lc, clause_kw)
            if tf_s <= 0.0 and not is_heading[idx]:
                # немає збігів і немає заголовка — ймовірність низька
                continue

            score = tf_s
            if is_heading[idx]:
                score += _heading_bonus(headings_lc[idx], clause_kw)
            score += _position_bonus(idx, total)

            if score >= min_score and (matched_terms or is_heading[idx]):
                preview = block.strip().replace("\n", " ")
                preview = preview[:200] + ("…" if len(preview) > 200 else "")
                out.append(
                    MatchCandidate(
                        clause_type=clause_type,
                        block_index=idx,
                        score=round(score, 6),  # стабільність порівнянь
                        matched_terms=tuple(matched_terms),
                        text_preview=preview,
                    )
                )

    # Детерміноване сортування: score ↓, block_index ↑, clause_type ↑
    out.sort(key=lambda c: (-c.score, c.block_index, c.clause_type))
    return out
