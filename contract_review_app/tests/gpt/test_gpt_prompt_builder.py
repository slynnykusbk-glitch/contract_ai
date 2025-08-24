"""
✅ Unit tests for GPT Prompt Builder (build_prompt).
Покривають типові та edge-випадки для формування коректного промпту на базі AnalysisOutput.
"""

import pytest
from contract_review_app.core.schemas import AnalysisOutput, Finding
from contract_review_app.gpt.gpt_prompt_builder import build_prompt


def test_build_prompt_full_content():
    """
    ✅ Перевіряє генерацію prompt з усіма елементами:
    - clause_type, status
    - findings із severity
    - recommendations
    - original clause
    """
    analysis = AnalysisOutput(
        clause_type="Confidentiality",
        status="FAIL",
        text="The receiving party shall not disclose any information...",
        findings=[
            Finding(code="F001", message="Clause is missing duration", severity="medium"),
            Finding(code="F002", message="Clause lacks definition of confidential information", severity="high"),
        ],
        recommendations=[
            "Add a confidentiality duration (e.g. 3-5 years).",
            "Define what constitutes confidential information.",
        ],
        diagnostics={
            "start_date": "No start date",
            "survival_clause": "Missing survival clause"
        }
    )

    prompt = build_prompt(analysis)

    # 🔍 Перевірка ключових блоків prompt-у
    assert "Clause Type: Confidentiality" in prompt
    assert "Status: FAIL" in prompt
    assert "Findings:" in prompt
    assert "- [medium] Clause is missing duration" in prompt
    assert "- [high] Clause lacks definition of confidential information" in prompt
    assert "Recommendations:" in prompt
    assert "- Add a confidentiality duration" in prompt
    assert "- Define what constitutes confidential information." in prompt
    assert "Original Clause:" in prompt
    assert "The receiving party shall not disclose any information" in prompt
    assert "Please provide the improved clause" in prompt