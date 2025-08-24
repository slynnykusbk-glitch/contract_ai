from __future__ import annotations

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Очікуємо наявність config.py поруч із пакетом програми
try:
    from contract_review_app.config import CLAUSE_KEYWORDS, ALIASES
except Exception as exc:  # захищаємося від помилок імпорту
    CLAUSE_KEYWORDS = {}  # type: ignore
    ALIASES = {}  # type: ignore
    logger.error("patterns: cannot import config (CLAUSE_KEYWORDS/ALIASES). %s", exc)


def _ensure_lower_list(lst: List[str]) -> List[str]:
    return sorted(
        {(s or "").strip().lower() for s in lst if isinstance(s, str) and s.strip()}
    )


def _normalize_keywords(raw_keywords: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Приводить:
      - ключі до lowercase;
      - значення до списків уникальних lowercase-рядків (відсортовано для детермінованості).
    Відкидає пусті ключі/списки.
    """
    out: Dict[str, List[str]] = {}
    for k, v in (raw_keywords or {}).items():
        if not isinstance(k, str) or not k.strip():
            continue
        key = k.strip().lower()
        if not isinstance(v, list) or not v:
            continue
        vals = _ensure_lower_list(v)
        if vals:
            out[key] = vals
    return dict(sorted(out.items(), key=lambda kv: kv[0]))  # детермінований порядок


def _normalize_aliases(raw_aliases: Dict[str, str]) -> Dict[str, str]:
    """
    Приводить псевдоніми до lowercase, відкидає некоректні/порожні.
    """
    out: Dict[str, str] = {}
    for k, v in (raw_aliases or {}).items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        kk = k.strip().lower()
        vv = v.strip().lower()
        if kk and vv:
            out[kk] = vv
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def load_clause_patterns() -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """
    Завантажує й нормалізує патерни клаузул:
      - keywords: Dict[clause_type_lower, List[keywords_lower]]
      - aliases:  Dict[alias_lower, canonical_lower]

    Валідація:
      - обидва словники не порожні;
      - усі ключі/значення — рядки (після нормалізації);
      - для alias-ів цільовий canonical повинен існувати серед keywords.
    """
    keywords = _normalize_keywords(
        CLAUSE_KEYWORDS if isinstance(CLAUSE_KEYWORDS, dict) else {}
    )
    aliases = _normalize_aliases(ALIASES if isinstance(ALIASES, dict) else {})

    if not keywords:
        logger.warning(
            "load_clause_patterns: empty or invalid CLAUSE_KEYWORDS after normalization."
        )
    if not aliases:
        logger.info(
            "load_clause_patterns: ALIASES is empty or invalid; continuing with empty aliases."
        )

    # Перевірка: aliases → canonical існує у keywords
    bad_alias_targets = {a for a in aliases.values() if a not in keywords}
    if bad_alias_targets:
        logger.warning(
            "load_clause_patterns: aliases point to unknown canonical keys: %r",
            sorted(bad_alias_targets),
        )
        # за правилом strict можна або відфільтрувати, або згенерувати помилку.
        # Фільтруємо небезпечні:
        aliases = {k: v for k, v in aliases.items() if v in keywords}

    return keywords, aliases
