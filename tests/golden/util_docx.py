from pathlib import Path
from typing import List

from docx import Document


def load_valid_docx(dirpath: Path) -> List[Path]:
    """Возвращает только действительно читаемые DOCX (исключая LFS-пойнтеры/битые файлы)."""
    docs: List[Path] = []
    for p in sorted(dirpath.glob("*.docx")):
        try:
            Document(p)  # проверка что это ZIP/DOCX
        except Exception:
            continue
        docs.append(p)
    return docs
