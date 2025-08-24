from contract_review_app.core.schemas import AnalysisOutput
from contract_review_app.gpt.gpt_proxy_api import call_gpt_api


def test_call_gpt_api_mock():
    clause_type = "Indemnity"
    prompt = "Rewrite this clause: The Seller shall not be liable for..."

    output = AnalysisOutput(
        clause_type=clause_type,
        text="The Seller shall not be liable for...",
        status="WARN",
        findings=[],
        recommendations=["Clarify the scope of liability"],
        problems=[],
        legal_basis=[],
        diagnostics={},
        trace=[],
        score=50,
    )

    response = call_gpt_api(clause_type=clause_type, prompt=prompt, output=output)

    assert isinstance(response.draft_text, str)
    assert response.draft_text.startswith("UPDATED:")
    assert "REVISED" in response.draft_text
    assert response.explanation is not None
