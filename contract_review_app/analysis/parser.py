from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Dict, List

from docx import Document
from pdfminer.high_level import extract_text

from contract_review_app.intake.parser import ParsedDocument as IntakeParsedDocument


@dataclass
class ParsedDoc:
    normalized_text: str
    offset_map: List[int]
    segments: List[Dict[str, object]]


_HEADING_RE = re.compile(r"^[A-Z0-9 .\-]{6,}$")
_NUMBERING_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)(?:\.)?\s+")
_SUBPOINT_RE = re.compile(r"^\(?([a-z]|[ivxlcdm]+|\d+)\)", re.IGNORECASE)


def _segment_lines(text: str) -> List[Dict[str, object]]:
    segments: List[Dict[str, object]] = []
    pos = 0
    lines = text.split("\n")
    for line in lines:
        start = pos
        end = start + len(line)
        pos = end + 1

        if line == "":
            continue

        kind = "paragraph"
        number = None
        heading_text = None

        m_num = _NUMBERING_RE.match(line)
        if _HEADING_RE.match(line) or m_num:
            kind = "heading"
            if m_num:
                number = m_num.group("num")
            heading_text = line
        else:
            m = _SUBPOINT_RE.match(line)
            if m:
                number = m.group(1)

        segments.append(
            {
                "id": len(segments) + 1,
                "kind": kind,
                "start": start,
                "end": end,
                "text": line,
                "heading": heading_text,
                "number": number,
                "parent_id": None,
            }
        )
    return segments


def parse_text(text: str) -> ParsedDoc:
    intake_doc = IntakeParsedDocument.from_text(text)
    segments = _segment_lines(intake_doc.normalized_text)
    return ParsedDoc(
        normalized_text=intake_doc.normalized_text,
        offset_map=intake_doc.offset_map,
        segments=segments,
    )


def parse_docx(data: bytes) -> ParsedDoc:
    document = Document(io.BytesIO(data))
    text = "\n".join(p.text for p in document.paragraphs)
    return parse_text(text)


def parse_pdf(data: bytes) -> ParsedDoc:
    text = extract_text(io.BytesIO(data)) or ""
    return parse_text(text)
