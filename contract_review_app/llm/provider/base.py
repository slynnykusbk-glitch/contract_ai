from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


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
    model: str = "mock-legal-v1"
    usage: Dict[str, Any] = field(default_factory=dict)


class LLMProvider:
    """Abstract base class for all LLM providers."""

    def generate(
        self, prompt: str, config: LLMConfig
    ) -> LLMResult:  # pragma: no cover - interface
        raise NotImplementedError
