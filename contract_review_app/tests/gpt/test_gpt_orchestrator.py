import pytest
from contract_review_app.gpt.gpt_orchestrator import run_gpt_drafting_pipeline
from contract_review_app.core.schemas import AnalysisOutput
from unittest.mock import patch

# ❗Мокаємо відповідь GPT
MOCK_RESPONSE = {
    "draft": "This is the new clause version.",
    "explanation": "Rewritten for clarity and legal accuracy.",
    "score": 0.98,
}

@pytest.fixture
def sample_analysis_output():
    return AnalysisOutput(
        clause_type="Confidentiality",
        status="WARN",
        findings=[],
        recommendations=[],
        diagnostics={"rule": "check_confidentiality", "rule_version": "1.0"},
        trace=["check_confidentiality"],
        score=0.65,
        category="Confidentiality",
        severity="medium",
        risk_level="medium",
        text="The Recipient shall maintain the confidentiality of all Discloser information...",
        law_reference=["UK GDPR", "Data Protection Act 2018"],
        keywords=["confidentiality", "discloser", "recipient"]
    )

def test_run_gpt_drafting_pipeline(sample_analysis_output):
    with patch("contract_review_app.gpt.gpt_orchestrator.call_gpt_api", return_value=MOCK_RESPONSE):
        updated = run_gpt_drafting_pipeline(sample_analysis_output)

        assert isinstance(updated, AnalysisOutput)
        assert updated.text == sample_analysis_output.text  # не змінюємо оригінал
        assert "Rewritten for clarity" in updated.recommendations[0]
        assert "This is the new clause" in updated.recommendations[0]
        assert updated.score >= sample_analysis_output.score
        assert "gpt_draft" in updated.diagnostics
