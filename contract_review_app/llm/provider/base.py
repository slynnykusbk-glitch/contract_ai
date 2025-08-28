from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for LLM providers.

    For now this class is intentionally minimal; fields can be extended later
    without breaking compatibility.
    """

    pass


@dataclass
class LLMResult:
    text: str
    provider: str


class LLMProvider:
    """Abstract base class for all LLM providers."""

    def generate(
        self, prompt: str, config: LLMConfig
    ) -> LLMResult:  # pragma: no cover - interface
        raise NotImplementedError
