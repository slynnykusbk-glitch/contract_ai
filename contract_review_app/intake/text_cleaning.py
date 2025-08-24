import re
import unicodedata
from typing import List

# Патерни для очищення
_RE_MULTI_SPACE = re.compile(r"[ \t]+")
_RE_MULTI_NL = re.compile(r"\n{3,}")

# Zero-width / керуючі невидимі символи, які часто «ламають» текст
# ZWSP..ZWNBSP, BOM, bidi control тощо
_ZERO_WIDTH = [
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2060",
    "\u2061",
    "\u2062",
    "\u2063",
    "\u2064",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\ufeff",
]
# NBSP → пробіл
_NBSP = "\u00a0"

# Часті артефакти OCR/копіювання, які слід прибрати як «сміття»
# (додав { і } — вони інколи «прилипають» від копіювань PDF/сканів)
_DENYLIST_CHARS = set(
    ["�", "¡", "×", "•", "·", "◦", "►", "■", "□", "◆", "◇", "*", "{", "}"]
)

# Виявляємо текстові escape-послідовності виду \xAB (не справжні байти, а саме текст "\xAB")
_ESCAPE_HEX_SEQ = re.compile(r"\\x[0-9A-Fa-f]{2}")

# Універсальний «словоподібний» клас для меж слів
_WORDISH = r"[A-Za-zА-Яа-яІіЇїЄє0-9’'\-]"


def normalize_whitespace(text: str) -> str:
    """
    Зводить пробіли до одного, колапсує >=3 переноси до подвійного.
    """
    if not isinstance(text, str):
        return text
    text = _RE_MULTI_SPACE.sub(" ", text)
    text = _RE_MULTI_NL.sub("\n\n", text)
    return text.strip()


def remove_control_characters(text: str) -> str:
    """
    Видаляє усі керуючі символи (категорія 'C*'), КРІМ \n та \t.
    """
    if not isinstance(text, str):
        return text
    out_chars: List[str] = []
    for ch in text:
        cat0 = unicodedata.category(ch)[0] if ch else "Z"
        if ch in ("\n", "\t"):
            out_chars.append(ch)
        elif cat0 == "C":
            # керуючі – прибираємо
            continue
        else:
            out_chars.append(ch)
    return "".join(out_chars)


def clean_punctuation_spacing(text: str) -> str:
    """
    Вирівнює пробіли перед/після пунктуації (, . ; : ! ?).
    """
    if not isinstance(text, str):
        return text
    # Прибрати пробіли ПЕРЕД пунктуацією
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    # Гарантувати пробіл ПІСЛЯ пунктуації (якщо далі літера/цифра)
    text = re.sub(r"([,.;:!?])(?=\S)", r"\1 ", text)
    return text


def _remove_escape_hex_with_spacing(text: str) -> str:
    """
    Видаляє текстові послідовності виду \\xNN.
    Якщо між «словоподібними» символами — вставляє пробіл, щоб не злипалося.
    """

    def repl(m: re.Match) -> str:
        start, end = m.span()
        left = text[start - 1 : start]
        right = text[end : end + 1]
        if re.match(_WORDISH, left or "") and re.match(_WORDISH, right or ""):
            return " "
        return ""

    return _ESCAPE_HEX_SEQ.sub(repl, text)


def remove_artifacts_and_garbage(text: str) -> str:
    """
    Видаляє/нормалізує типові артефакти:
      - BOM/zero-width/bidi-контроли;
      - NBSP -> звичайний пробіл;
      - специфічні «сміттєві» символи (denylist);
      - текстові escape-послідовності \\xAB (із запобіганням злипання слів);
      - відомі комбінації «ï»¿», «�».
    Зберігає кирилицю/латиницю/цифри/стандартну пунктуацію.
    """
    if not isinstance(text, str):
        return text

    # NFKC нормалізація (уніфікує представлення)
    text = unicodedata.normalize("NFKC", text)

    # NBSP -> звичайний пробіл
    text = text.replace(_NBSP, " ")

    # Прибрати zero-width та BOM/бідi-контроли
    for z in _ZERO_WIDTH:
        if z in text:
            text = text.replace(z, "")

    # Відомі послідовності з битого BOM/кодеків
    text = text.replace("ï»¿", "")  # UTF-8 BOM, розбитий при декодуванні
    text = text.replace("�", "")  # replacement character

    # Текстові escape-послідовності типу \xAB (зі збереженням пробілу між словами)
    text = _remove_escape_hex_with_spacing(text)

    # Прибрати персонажі з denylist
    if any(ch in text for ch in _DENYLIST_CHARS):
        text = "".join(ch for ch in text if ch not in _DENYLIST_CHARS)

    # Додаткова «обережна» фільтрація: прибрати поодинокі «сиротливі» знаки ×, ¡ між літерами
    text = re.sub(rf"(?<={_WORDISH})[×¡](?={_WORDISH})", "", text)

    return text


def preprocess_text(text: str) -> str:
    """
    Повний пайплайн очищення. Порядок важливий:
      1) remove_artifacts_and_garbage  — спершу прибираємо артефакти/невидимі/escape;
      2) remove_control_characters     — потім прибираємо керуючі коди;
      3) normalize_whitespace          — нормалізуємо пробіли/переноси після видалень;
      4) clean_punctuation_spacing     — вирівнюємо інтервали навколо пунктуації.
    """
    if not isinstance(text, str):
        return text
    text = remove_artifacts_and_garbage(text)
    text = remove_control_characters(text)
    text = normalize_whitespace(text)
    text = clean_punctuation_spacing(text)
    return text
