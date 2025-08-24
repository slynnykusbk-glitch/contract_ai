import pytest
from contract_review_app.core.schemas import AnalysisOutput, GPTDraftResponse
from contract_review_app.gpt.gpt_prompt_builder import build_prompt
from contract_review_app.gpt.gpt_proxy_api import call_gpt_api
from contract_review_app.gpt.gpt_draft_engine import generate_clause_draft

def test_end_to_end_gpt_pipeline():
    # Вхідні дані
    output = AnalysisOutput(
        clause_type="Confidentiality",
        text="The parties agree to keep all information confidential.",
        status="FAIL",
        findings=[],
        recommendations=["Clarify what information is considered confidential."],
        diagnostics={"rule": "confidentiality_check", "rule_version": "1.0"},
        trace=[],
        score=40,
    )

    # Побудова prompt
    prompt = build_prompt(output)
    assert isinstance(prompt, str)
    assert "Confidentiality" in prompt
    assert "recommendation" in prompt.lower()

    # Виклик мок GPT API
    response = call_gpt_api(clause_type=output.clause_type, prompt=prompt, output=output)
    assert isinstance(response, GPTDraftResponse)
    assert response.draft_text.startswith("UPDATED:")
    assert "REVISED based on recommendation" in response.draft_text
    assert "issues identified" in response.explanation
    assert response.score == 90

    # Повна генерація через generate_clause_draft
    final = generate_clause_draft(output)
    assert isinstance(final, GPTDraftResponse)
    assert final.original_text == output.text
    assert final.clause_type == output.clause_type
    assert final.draft_text == response.draft_text
    assert final.explanation == response.explanation
    assert "Confidentiality" in final.title
