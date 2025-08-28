from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from .api_dto import DraftRequest, SuggestEditsRequest, LLMResponse

try:  # pragma: no cover - prefer real orchestrator if available
    from .orchestrator import Orchestrator  # type: ignore
except Exception:  # pragma: no cover - fallback mock

    class Orchestrator:  # type: ignore
        """Deterministic mock orchestrator used in tests."""

        provider = "mock"
        model = "mock-legal-v1"

        def _build_prompt(
            self, question: str, context_text: str, citations: List[Dict[str, Any]]
        ) -> str:
            labels = [
                f"{c.get('instrument', '')} §{c.get('section', '')}".strip()
                for c in citations
            ]
            evidence = "\n".join(labels)
            return f"{question}\n\n<<EVIDENCE>>\n{evidence}".strip()

        def draft(
            self,
            question: str,
            context_text: str,
            citations: List[Dict[str, Any]],
        ) -> Dict[str, Any]:
            prompt = self._build_prompt(question, context_text, citations)
            return {
                "provider": self.provider,
                "model": self.model,
                "result": f"Draft: {question}",
                "prompt": prompt,
                "verification_status": "unverified",
                "grounding_trace": {"citations": citations},
                "usage": {},
            }

        def suggest_edits(
            self,
            question: str,
            context_text: str,
            citations: List[Dict[str, Any]],
        ) -> Dict[str, Any]:
            prompt = self._build_prompt(question, context_text, citations)
            return {
                "provider": self.provider,
                "model": self.model,
                "result": f"Suggest: {question}",
                "prompt": prompt,
                "verification_status": "unverified",
                "grounding_trace": {"citations": citations},
                "usage": {},
            }


router = APIRouter(tags=["llm"])


@router.post("/draft", response_model=LLMResponse)
def api_draft(req: DraftRequest) -> LLMResponse:
    orch = Orchestrator()  # ProxyProvider → Mock by default
    out = orch.draft(
        question=req.question,
        context_text=req.context_text,
        citations=[c.model_dump() for c in req.citations],
    )
    return LLMResponse(**out)


@router.post("/suggest_edits", response_model=LLMResponse)
def api_suggest(req: SuggestEditsRequest) -> LLMResponse:
    orch = Orchestrator()
    out = orch.suggest_edits(
        question=req.question,
        context_text=req.context_text,
        citations=[c.model_dump() for c in req.citations],
    )
    return LLMResponse(**out)
