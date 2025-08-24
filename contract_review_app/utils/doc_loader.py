# contract_review_app/utils/doc_loader.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
import docx

def load_docx_text(file_path: str | Path) -> str:
    """
    Завантажує текст із .docx файлу як єдиний рядок.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {file_path}")

    doc = docx.Document(path)
    return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
