from __future__ import annotations

import logging
import os
from typing import List

# python-docx є рекомендованим, але не обов'язковим:
try:
    from docx import Document  # type: ignore
except Exception:  # пакет може бути відсутній — обробимо це нижче
    Document = None  # type: ignore

logger = logging.getLogger(__name__)


def _is_docx(path: str) -> bool:
    return isinstance(path, str) and path.lower().endswith(".docx")


def _join_paragraphs(paragraphs: List[str]) -> str:
    # Прибираємо повністю порожні/whitespace параграфи, об'єднуємо через \n
    cleaned = [p.strip() for p in paragraphs if isinstance(p, str) and p and p.strip()]
    return "\n".join(cleaned).strip()


def load_docx_text(path: str) -> str:
    """
    Завантажує текст із .docx у вигляді суцільного рядка (параграфи через '\\n').

    Правила:
      - якщо файл не існує або не .docx — повертає '' і лог warning;
      - якщо docx пошкоджений або читання неможливе — повертає '' і лог error;
      - ігнорує порожні параграфи (залишає тільки non-empty).

    Повертає:
      - об'єднаний текст або ''.
    """
    if not _is_docx(path):
        logger.warning(
            "load_docx_text: unsupported file type (expected .docx): %r", path
        )
        return ""

    if not os.path.exists(path):
        logger.warning("load_docx_text: file does not exist: %r", path)
        return ""

    if Document is None:
        logger.error(
            "load_docx_text: python-docx is not installed; cannot read %r", path
        )
        return ""

    try:
        doc = Document(path)  # type: ignore
        paragraphs: List[str] = [
            p.text for p in getattr(doc, "paragraphs", [])
        ]  # safe getattr
        return _join_paragraphs(paragraphs)
    except Exception as exc:
        logger.exception("load_docx_text: failed to read %r: %s", path, exc)
        return ""
