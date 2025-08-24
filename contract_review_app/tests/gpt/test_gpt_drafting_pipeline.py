# 📄 contract_review_app/tests/gpt/test_gpt_drafting_pipeline.py

from contract_review_app.core.schemas import AnalysisOutput
from contract_review_app.gpt.gpt_draft_engine import generate_clause_draft
from contract_review_app.gpt.gpt_dto import GPTDraftResponse


def test_generate_clause_draft():
    analysis = AnalysisOutput(
        clause_type="Confidentiality",
        text="The parties shall keep all information secret.",
        status="FAIL",
        findings=[
            {
                "code": "missing-term",
                "message": "No duration specified for confidentiality.",
                "severity": "high",
                "evidence": "Missing duration",
                "legal_basis": ["UK GDPR"]
            }
        ],
        recommendations=["Add duration of confidentiality (e.g., 3–5 years)."],
        diagnostics=["Missing time period"],
        trace=["rule_engine_checked"]
    )

    result: GPTDraftResponse = generate_clause_draft(analysis)

    assert isinstance(result, GPTDraftResponse)
    assert "draft_text" in result.dict()
    assert result.draft_text.strip() != ""
