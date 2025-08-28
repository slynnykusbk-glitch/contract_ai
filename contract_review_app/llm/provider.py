from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class LLMConfig:
    """Minimal configuration for LLM requests."""

    temperature: float = 0.0
    top_p: float = 1.0


@dataclass
class LLMResult:
    """Container for LLM responses."""

    text: str
    usage: Any
    model: str = ""
    provider: str = ""


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    def generate(self, prompt: str, config: LLMConfig) -> LLMResult: ...
