import re
from typing import List

# Безпечний regex заголовка: дефіс наприкінці класу, дозволені en/em dashes.
_HEADING_RE = re.compile(
    r"""^(
        [A-Z][A-Z0-9 &/–—-]+$                 # ALL CAPS/UPPER heading
        |
        \d+(?:\.\d+)*[.)]?\s+[A-Z].{0,120}$   # 1., 1.1., 2) + короткий Title Case
    )""",
    re.X,
)

_NUMBERED_ITEM_RE = re.compile(r"^\s*(\d+(?:\.\d+)*[.)])\s+")
_ALPHA_ITEM_RE = re.compile(r"^\s*([A-Za-z][.)])\s+")

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[\.!?])\s+(?=[A-ZА-ЯІЇЄ])")

# Фінальна пунктуація, яка «закриває» речення/абзац
_END_PUNCT_RE = re.compile(r"[\.!?:]$")


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_on_paragraphs(text: str) -> List[str]:
    # Розбивка на абзаци за \n\n+
    parts = re.split(r"\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def _further_split_on_list_items(block: str) -> List[str]:
    """
    Дорозбиття абзацу на підблоки:
      - нові підблоки з нумерованих/літерних елементів або заголовків;
      - *нове*: якщо попередній рядок не закінчується пунктуацією, а наступний починається з малої
        літери — вважаємо це розірваним реченням і починаємо новий підблок.
    """
    lines = [ln.rstrip() for ln in block.split("\n")]
    chunks: List[str] = []
    buf: List[str] = []

    def flush():
        if buf:
            chunks.append("\n".join(buf).strip())
            buf.clear()

    prev_line = ""
    for ln in lines:
        ln_stripped = ln.strip()
        is_numbered = bool(_NUMBERED_ITEM_RE.match(ln))
        is_alpha = bool(_ALPHA_ITEM_RE.match(ln))
        is_heading = bool(_HEADING_RE.match(ln_stripped))

        # евристика «розірваного речення» на одинарному переносі
        broken_sentence_boundary = False
        if prev_line:
            if not _END_PUNCT_RE.search(prev_line.strip()) and (
                ln_stripped[:1].islower()
            ):
                broken_sentence_boundary = True

        if (is_numbered or is_alpha or is_heading or broken_sentence_boundary) and buf:
            flush()

        buf.append(ln)
        prev_line = ln
    flush()
    return [c for c in chunks if c]


def _maybe_split_long_block_into_sentences(
    block: str, sentence_split_over: int
) -> List[str]:
    if len(block) < sentence_split_over:
        return [block.strip()]
    # Розбиваємо дуже довгі абзаци на речення (крапка/!? + велика літера)
    sents = _SENTENCE_BOUNDARY_RE.split(block.strip())
    sents = [s.strip() for s in sents if s and s.strip()]
    return sents if sents else [block.strip()]


def _looks_like_heading(text: str) -> bool:
    line = text.strip()
    if not line:
        return False
    if _HEADING_RE.match(line):
        return True
    # Додаткова евристика заголовка
    if len(line) <= 80 and not line.endswith("."):
        words = line.split()
        if words and sum(w.isupper() for w in words) >= max(1, len(words) // 2):
            return True
    return False


def _merge_short_blocks(blocks: List[str], min_len: int) -> List[str]:
    """
    Мердж коротких блоків, але:
      - *нове*: якщо поточний блок завершується фінальною пунктуацією
        і наступний починається з великої літери або виглядає як заголовок — НЕ мерджимо
        (ймовірно, це різні абзаци).
    """
    if not blocks:
        return []
    merged: List[str] = []
    i = 0
    while i < len(blocks):
        cur = blocks[i].strip()
        if _looks_like_heading(cur) and i + 1 < len(blocks):
            nxt = blocks[i + 1].strip()
            merged.append((cur + "\n" + nxt).strip())
            i += 2
            continue

        if len(cur) < min_len and i + 1 < len(blocks):
            nxt = blocks[i + 1].strip()

            # захист від небажаного мерджу різних абзаців
            if _END_PUNCT_RE.search(cur) and (
                nxt[:1].isupper() or _looks_like_heading(nxt)
            ):
                merged.append(cur)  # залишаємо як окремий короткий абзац
                i += 1
                continue

            merged.append((cur + " " + nxt).strip())
            i += 2
        else:
            merged.append(cur)
            i += 1
    return [b for b in merged if b]


def _merge_broken_sentences(blocks: List[str]) -> List[str]:
    """
    Якщо блок закінчується без завершальної пунктуації, а наступний починається з малої літери —
    зливаємо їх (підтримуємо кейс із _further_split_on_list_items).
    """
    if not blocks:
        return []
    out: List[str] = []
    i = 0
    while i < len(blocks):
        cur = blocks[i].strip()
        if i + 1 < len(blocks):
            nxt = blocks[i + 1].strip()
            if (not _END_PUNCT_RE.search(cur)) and nxt and nxt[:1].islower():
                out.append((cur + " " + nxt).strip())
                i += 2
                continue
        out.append(cur)
        i += 1
    return out


def split_into_candidate_blocks(
    text: str,
    *,
    min_len: int = 60,
    sentence_split_over: int = 800,
) -> List[str]:
    """
    Розбиває сирий текст контракту на кандидатні блоки:
    1) \n\n абзаци;
    2) нумеровані/літерні елементи списку/заголовки з нового рядка;
    3) довгі абзаци — на речення (для дуже великих шматків);
    4) мердж коротких блоків і заголовків (із захистом від небажаного злиття різних абзаців);
    5) мердж "розірваних" речень.
    """
    if not isinstance(text, str):
        return []

    text = _normalize_newlines(text)
    paragraphs = _split_on_paragraphs(text)

    # Дорозбиття кожного абзацу на підблоки за маркерами списків/заголовків/розірваним реченням
    blocks: List[str] = []
    for p in paragraphs:
        for chunk in _further_split_on_list_items(p):
            blocks.extend(
                _maybe_split_long_block_into_sentences(chunk, sentence_split_over)
            )

    # Почистити від пустих
    blocks = [b.strip() for b in blocks if b and b.strip()]

    # Мердж коротких і заголовків (із захистом)
    blocks = _merge_short_blocks(blocks, min_len=min_len)

    # Мердж розірваних речень
    blocks = _merge_broken_sentences(blocks)

    # Фінальний фільтр
    final = [b.strip() for b in blocks if b and b.strip()]
    return final
