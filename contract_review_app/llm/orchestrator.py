# contract_review_app/llm/orchestrator.py
from __future__ import annotations

from typing import Any, Dict, Optional

from .provider.base import LLMConfig, LLMProvider
from .provider.proxy import ProxyProvider
from .prompt_builder import build_prompt
from .citation_resolver import make_grounding_pack
from .verification import verify_output_contains_citations


class Orchestrator:
    """Deterministic LLM orchestrator:
    - builds grounding pack from question/context/citations,
    - renders strict prompt,
    - calls provider (default: ProxyProvider → mock),
    - verifies output against evidence and returns status/trace.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        config: Optional[LLMConfig] = None,
    ) -> None:
        self.provider = provider or ProxyProvider()
        self.config = config or LLMConfig()

    def draft(
        self, *, question: str = "", context_text: str = "", citations: Any = None
    ) -> Dict[str, Any]:
        gp = make_grounding_pack(question, context_text, citations)
        prompt = build_prompt("draft", gp)
        res = self.provider.generate(prompt, self.config)
        status = verify_output_contains_citations(res.text, gp.get("evidence") or [])
        return {
            "prompt": prompt,
            "result": res.text,
            "usage": res.usage,
            "model": res.model,
            "provider": res.provider,
            "verification_status": status,
            "grounding_trace": {
                "citations": gp.get("citations", []),
                "evidence": gp.get("evidence", []),
            },
        }

    def suggest_edits(
        self, *, question: str = "", context_text: str = "", citations: Any = None
    ) -> Dict[str, Any]:
        gp = make_grounding_pack(question, context_text, citations)
        prompt = build_prompt("suggest_edits", gp)
        res = self.provider.generate(prompt, self.config)
        status = verify_output_contains_citations(res.text, gp.get("evidence") or [])
        return {
            "prompt": prompt,
            "result": res.text,
            "usage": res.usage,
            "model": res.model,
            "provider": res.provider,
            "verification_status": status,
            "grounding_trace": {
                "citations": gp.get("citations", []),
                "evidence": gp.get("evidence", []),
            },
        }
