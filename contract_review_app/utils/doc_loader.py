# contract_review_app/utils/doc_loader.py
from __future__ import annotations
from pathlib import Path
from typing import Iterable

import docx
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def _iter_block_items(parent) -> Iterable[Paragraph | Table]:
    """Yield paragraphs and tables in document order."""

    body = parent.element.body  # type: ignore[attr-defined]
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def load_docx_text(file_path: str | Path) -> str:
    """Load text from a ``.docx`` file preserving logical structure.

    Bullet/numbered list markers are removed by ``python-docx`` and we simply
    join paragraph texts with ``\n``.  Tables are converted so that cell texts in
    a row are joined by ``\t`` and rows are separated by ``\n``.
    """

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не знайдено: {file_path}")

    doc = docx.Document(path)
    lines: list[str] = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                lines.append(text)
        else:  # Table
            for row in block.rows:
                cells = []
                for cell in row.cells:
                    cell_text = "\n".join(p.text for p in cell.paragraphs).strip()
                    cells.append(cell_text)
                row_text = "\t".join(cells).strip()
                if row_text:
                    lines.append(row_text)

    return "\n".join(lines)
