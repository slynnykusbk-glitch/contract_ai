import os
import tempfile
import pytest

from contract_review_app.intake.loader import load_docx_text

docx = pytest.importorskip("docx", reason="python-docx is required for these tests")
from docx import Document  # type: ignore


def _make_docx(paragraphs):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    tmp.close()
    d = Document()
    for text in paragraphs:
        d.add_paragraph(text)
    d.save(tmp.name)
    return tmp.name


def test_load_docx_text_success_basic():
    path = _make_docx(
        [
            "Definitions",
            "",
            "This Agreement sets out terms.",
            "Governing Law: England and Wales.",
        ]
    )
    try:
        out = load_docx_text(path)
        assert "Definitions" in out
        assert "This Agreement sets out terms." in out
        assert "Governing Law: England and Wales." in out
        # порожній параграф має бути відфільтрований
        assert "\n\n" not in out
    finally:
        os.unlink(path)


def test_load_docx_ignores_empty_paragraphs():
    path = _make_docx(["", "   ", "Non-empty"])
    try:
        out = load_docx_text(path)
        assert out == "Non-empty"
    finally:
        os.unlink(path)


def test_load_docx_returns_empty_for_nonexistent():
    out = load_docx_text("/no/such/file/sample_contract.docx")
    assert out == ""


def test_load_docx_returns_empty_for_wrong_extension(tmp_path):
    p = tmp_path / "not_a_doc.txt"
    p.write_text("Hello")
    out = load_docx_text(str(p))
    assert out == ""
