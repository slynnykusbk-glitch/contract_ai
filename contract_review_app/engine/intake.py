# contract_review_app/engine/intake.py
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

# SSOT типи (Pydantic v2)
try:
    from contract_review_app.core.schemas import Span, Clause, DocIndex
except Exception:
    pass
# -------------------------- Константи / патерни --------------------------

# Заголовки розділів і клауз (детерміновані евристики)
# - Section/Clause/Article <num>
# - "1.", "1)", "A)", "I.", тощо на початку рядка
# - Рядки "великою" з двокрапкою в кінці (e.g., CONFIDENTIALITY:)
HEADER_RE = re.compile(
    r"""(?mx)
    ^(?P<hdr>
        (?:
            (?:section|clause|article)\s+[0-9A-Za-z.\-]+   # Section 5.1 / Clause 10A / Article IV
            |
            (?:[0-9]{1,3}|[A-Z]|[IVXLCM]+)[\.\)]          # 1. / 1) / A) / IV.
        )
        [ \t]+(?P<title>[^\n]{3,})                         # назва
      |
        (?P<shout>[A-Z][A-Z \-/]{3,}):\s*$                 # SHOUTING HEADER:
    )
    """,
    re.IGNORECASE,
)

# Абзац як fallback: два й більше нових рядки як розділювач
PARA_SPLIT_RE = re.compile(r"\n{2,}", re.M)

# Ключові слова → типи клауз (класифікація заголовка/фрагмента)
TYPE_KEYWORDS = [
    ("termination", "termination"),
    ("indemnity", "indemnity"),
    ("governing law", "governing_law"),
    ("jurisdiction", "jurisdiction"),
    ("confidential", "confidentiality"),
    ("data protection", "data_protection"),
    ("gdpr", "data_protection"),
    ("limitation of liability", "limitation_of_liability"),
    ("liability", "limitation_of_liability"),
    ("force majeure", "force_majeure"),
    ("payment", "payment"),
    ("fees", "payment"),
    ("notice", "notice"),
    ("definitions", "definitions"),
    ("intellectual property", "ip"),
    ("ip", "ip"),
    ("assignment", "assignment"),
    ("severability", "severability"),
    ("entire agreement", "entire_agreement"),
]

# -------------------------- Хеші / ідентифікатори --------------------------


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _siphash64(data: bytes, key: bytes) -> str:
    """
    Псевдо-siphash 64b: намагаємося використати pysiphash, якщо доступний.
    Інакше — BLAKE2b(keyed, digest_size=8) як стабільний та швидкий фолбек.
    """
    try:
        # pysiphash: pip install siphash
        from siphash import siphash

        h = siphash(key, data)
        return f"{int(h):016x}"
    except Exception:
        h = hashlib.blake2b(data, digest_size=8, key=key).hexdigest()
        return h


def _stable_clause_id(start: int, length: int, fragment_hash: str) -> str:
    # Ключ для keyed-hash (стала сіль для детермінізму; у проді можна зберігати в конфігу)
    key = b"contract.ai/sipkey1"
    payload = f"{start}|{length}|{fragment_hash}".encode("utf-8")
    return _siphash64(payload, key)


def _anchor_hash(s: str) -> str:
    # Якорі короткі: достатньо 16 hex (64 біти) для переприв’язки
    return _sha256_str(s)[:16]


# -------------------------- Утіліти сегментації --------------------------


def _normalize_newlines(text: str) -> str:
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _detect_type(header_text: str, body_text: str) -> str:
    src = f"{header_text}\n{body_text}".lower()
    for key, t in TYPE_KEYWORDS:
        if key in src:
            return t
    return "paragraph"


def _dedupe_sorted(points: List[int], n: int) -> List[int]:
    pts = sorted(p for p in points if 0 <= p < n)
    out: List[int] = []
    last = None
    for p in pts:
        if last is None or p != last:
            out.append(p)
            last = p
    return out


# -------------------------- Основна функція --------------------------


def segment_document(text: str, language: Optional[str] = None) -> DocIndex:
    """
    Розбиття документа на клауза з zero-copy spans та стабільними id/якорами.
    - Детерміновані евристики заголовків/списків/секцій
    - Fallback: параграфи через порожні рядки
    - Clause.id = siphash(start|length|sha256(fragment))
    - anchors.pre_hash / anchors.post_hash для переприв’язки
    """
    raw = _normalize_newlines(text or "")
    n = len(raw)

    # Порожній документ → валідний DocIndex без клауз
    if n == 0:
        try:
            return DocIndex(document_name=None, language=language, clauses=[])
        except Exception:
            return DocIndex(clauses=[])

    # 1) Кандидатні межі за заголовками
    header_starts: List[int] = [m.start() for m in HEADER_RE.finditer(raw)]
    # 2) Якщо немає заголовків — розіб'ємо за абзацами (подвійні переноси)
    if not header_starts:
        # розділяємо на блоки-параграфи
        blocks = []
        last = 0
        for m in PARA_SPLIT_RE.finditer(raw):
            s, e = m.span()
            if last < s:
                blocks.append((last, s))
            last = e
        if last < n:
            blocks.append((last, n))
    else:
        # формуємо блоки від заголовка до наступного заголовка/кінця
        boundaries = _dedupe_sorted(header_starts + [n], n + 1)
        blocks = [
            (boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)
        ]
        # фільтр: прибрати «порожні»/дуже короткі (менше 2 символів)
        blocks = [(s, e) for (s, e) in blocks if e - s >= 2]

    clauses: List[Clause] = []
    for s, e in blocks:
        frag = raw[s:e]

        # Визначити заголовок у межах блоку (перший рядок, що схожий на заголовок)
        header_line = ""
        m = HEADER_RE.match(frag)
        if m:
            if m.group("title"):
                header_line = m.group("title").strip()
            elif m.group("hdr"):
                header_line = m.group("hdr").strip()
            elif m.group("shout"):
                header_line = (m.group("shout") or "").strip().rstrip(":")
        else:
            header_line = frag.strip().split("\n", 1)[0][:120]

        # Тип клауза
        ctype = _detect_type(header_line, frag)

        # Zero-copy span
        start = s
        length = max(0, e - s)

        # Фрагмент-хеш
        frag_hash = _sha256_str(raw[start : start + length])

        # Стабільний ідентифікатор
        cid = _stable_clause_id(start, length, frag_hash)

        # Якорі: 64 символи контексту до/після (обрізати межами)
        pre_start = max(0, start - 64)
        pre_hash = _anchor_hash(raw[pre_start:start])
        post_end = min(n, start + length + 64)
        post_hash = _anchor_hash(raw[start + length : post_end])

        # Побудова об'єкта Clause з захистом від суворих моделей
        span_obj = Span(start=start, length=length)
        clause_dict: Dict[str, Any] = {
            "id": cid,
            "type": ctype,
            "span": span_obj,
            "text": frag,
            "title": header_line[:160] if header_line else "",
            "anchors": {"pre_hash": pre_hash, "post_hash": post_hash},
            "hash": frag_hash[:16],
        }
        try:
            clause = Clause(**clause_dict)  # основний шлях
        except Exception:
            # fallback без anchors/hash (раптом модель сувора)
            clause = Clause(
                id=cid,
                type=ctype,
                span=span_obj,
                text=frag,
                title=header_line[:160] if header_line else "",
            )
        clauses.append(clause)

    try:
        return DocIndex(document_name=None, language=language, clauses=clauses)
    except Exception:
        return DocIndex(clauses=clauses)
