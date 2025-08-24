import pytest
from contract_review_app.gpt.gpt_draft_engine import generate_clause_draft, GPTDraftResponse
from contract_review_app.core.schemas import AnalysisOutput


def test_generate_clause_draft_returns_valid_response():
    output = AnalysisOutput(
        clause_type="Confidentiality",
        text="The parties agree to keep all information confidential.",
        status="FAIL",
        findings=[],
        recommendations=["Clarify what information is considered confidential."],
        diagnostics={"rule": "confidentiality_check", "rule_version": "1.0"},
        trace=[],
        score=42,
    )

    response = generate_clause_draft(output)

    assert isinstance(response, GPTDraftResponse)
    assert response.clause_type == "Confidentiality"
    assert response.original_text == output.text
    assert "Confidentiality" in (response.title or "")
    assert "confidential" in response.draft_text.lower()
    assert response.score >= 0
    assert response.explanation
    assert "suggested" in response.explanation.lower() or "revised" in response.explanation.lower()
