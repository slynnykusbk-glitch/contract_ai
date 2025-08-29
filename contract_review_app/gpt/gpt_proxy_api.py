# contract_review_app/gpt/gpt_proxy_api.py
# ASCII-only. Deterministic mock for GPT drafting with light guardrails.
from __future__ import annotations

from typing import Optional

from contract_review_app.core.schemas import AnalysisOutput
from contract_review_app.gpt.gpt_dto import GPTDraftResponse


def call_gpt_api(
    clause_type: str,
    prompt: str,
    output: AnalysisOutput,
    model: Optional[str] = "proxy-llm",
) -> GPTDraftResponse:
    """
    Deterministic mock of a GPT drafting endpoint used for tests.
    Always returns a draft starting with "UPDATED:" and mentioning a revision.
    """
    base_text = (getattr(output, "text", "") or "").strip()
    recommendation = ""
    try:
        recommendation = (output.recommendations or [""])[0]
    except Exception:
        pass

    draft_text = (
        f"UPDATED: {base_text}\nREVISED based on recommendation: {recommendation}"
        if base_text
        else "UPDATED: \nREVISED based on recommendation:"
    )

    explanation = (
        "Suggested revision based on issues identified during rule analysis."
    )

    return GPTDraftResponse(
        draft_text=draft_text,
        explanation=explanation,
        score=90,
        original_text=base_text,
        clause_type=clause_type,
        status="ok",
        title=f"Drafted: {clause_type}",
    )
