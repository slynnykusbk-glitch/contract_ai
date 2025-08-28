from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

from .base import LLMProvider, LLMConfig, LLMResult
from .mock_provider import MockProvider


# Stub providers ------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    def generate(
        self, prompt: str, config: LLMConfig
    ) -> LLMResult:  # pragma: no cover - stub
        raise NotImplementedError("OpenAIProvider not yet implemented")


class AzureProvider(LLMProvider):
    def generate(
        self, prompt: str, config: LLMConfig
    ) -> LLMResult:  # pragma: no cover - stub
        raise NotImplementedError("AzureProvider not yet implemented")


class AnthropicProvider(LLMProvider):
    def generate(
        self, prompt: str, config: LLMConfig
    ) -> LLMResult:  # pragma: no cover - stub
        raise NotImplementedError("AnthropicProvider not yet implemented")


# Registry -----------------------------------------------------------------


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, LLMProvider] = {
            "mock": MockProvider(),
            "openai": OpenAIProvider(),
            "azure": AzureProvider(),
            "anthropic": AnthropicProvider(),
        }

    def get(self, name: str) -> LLMProvider:
        if name not in self._providers:
            raise KeyError(f"Unknown provider: {name}")
        return self._providers[name]


# Proxy provider ------------------------------------------------------------


class ProxyProvider(LLMProvider):
    def __init__(self, registry: Optional[ProviderRegistry] = None) -> None:
        self.registry = registry or ProviderRegistry()
        raw = os.getenv("CONTRACTAI_LLM_PROVIDERS", "mock")
        self.providers_order: List[str] = [
            p.strip().lower() for p in raw.split(",") if p.strip()
        ]
        self.max_retries: int = int(os.getenv("CONTRACTAI_LLM_MAX_RETRIES", "2"))

    def generate(self, prompt: str, config: LLMConfig) -> LLMResult:
        last_exc: Optional[Exception] = None
        for name in self.providers_order:
            provider = self.registry.get(name)
            for attempt in range(1, self.max_retries + 1):
                try:
                    return provider.generate(prompt, config)
                except NotImplementedError as e:
                    last_exc = e
                    break  # provider unsupported; try next
                except Exception as e:  # pragma: no cover - deterministic retry
                    last_exc = e
                    if attempt < self.max_retries:
                        time.sleep(0.01)
                        continue
                    break
        if last_exc:
            raise last_exc
        raise RuntimeError("No providers available")
