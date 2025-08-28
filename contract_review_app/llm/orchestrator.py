from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .provider import LLMConfig, LLMProvider, LLMResult
from .provider.proxy import ProxyProvider


@dataclass
class Query:
    question: str
    context: str


class Orchestrator:
    """Simple orchestrator routing prompts through an LLM provider."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        config: Optional[LLMConfig] = None,
    ) -> None:
        self.provider = provider or ProxyProvider()
        self.config = config or LLMConfig()

    def _compose_prompt(self, question: str, context: str) -> str:
        return f"{question}\n{context}".strip()

    def draft(self, question: str, context: str) -> LLMResult:
        prompt = self._compose_prompt(question, context)
        return self.provider.generate(prompt, self.config)

    def suggest_edits(self, question: str, context: str) -> LLMResult:
        prompt = self._compose_prompt(question, context)
        return self.provider.generate(prompt, self.config)
