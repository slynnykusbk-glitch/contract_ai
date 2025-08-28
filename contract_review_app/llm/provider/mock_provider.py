from __future__ import annotations

from .base import LLMProvider, LLMConfig, LLMResult


class MockProvider(LLMProvider):
    """Deterministic mock provider used for tests and local development."""

    def generate(self, prompt: str, config: LLMConfig) -> LLMResult:
        return LLMResult(text=f"MOCK:{prompt}", provider="mock")
