import json
from pathlib import Path

from contract_review_app.core.schemas import AnalysisOutput, Finding
from contract_review_app.disagreement_protocol import generate_disagreement_protocol


def _sample_outputs():
    orig = AnalysisOutput(
        clause_id="1",
        clause_type="data_protection",
        text="Original clause text",
        status="FAIL",
        findings=[
            Finding(
                code="missing.dp",
                message="Отсутствует положение о защите данных",
                legal_basis=["GDPR"],
            )
        ],
        recommendations=["Добавить условие о защите данных"],
    )
    fixed = AnalysisOutput(
        clause_id="1",
        clause_type="data_protection",
        text="Updated clause text",
        status="OK",
    )
    return [orig], [fixed]


def test_generate_disagreement_protocol(tmp_path: Path):
    original, updated = _sample_outputs()
    docx_file = tmp_path / "protocol.docx"
    json_file = tmp_path / "protocol.json"

    generate_disagreement_protocol(original, updated, docx_file, json_file)

    assert docx_file.exists()
    assert json_file.exists()

    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data[0]["clauseId"] == "1"
    assert data[0]["status"] == "fixed"

    from docx import Document

    doc = Document(docx_file)
    combined = "\n".join(p.text for p in doc.paragraphs)
    assert "Протокол разногласий" in combined
    assert "Отсутствует положение о защите данных" in combined
