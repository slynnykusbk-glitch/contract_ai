from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class DraftResult:
    text: str
    meta: Dict[str, Any]


@dataclass
class SuggestResult:
    items: List[Dict[str, Any]]
    meta: Dict[str, Any]


@dataclass
class QAResult:
    items: List[Dict[str, Any]]
    meta: Dict[str, Any]


class ProviderError(Exception):
    def __init__(self, provider: str, detail: str):
        super().__init__(detail)
        self.provider = provider
        self.detail = detail


class ProviderTimeoutError(ProviderError):
    def __init__(self, provider: str, timeout: float):
        super().__init__(provider, f"{provider} timeout {timeout}s")
        self.timeout = timeout


class ProviderAuthError(ProviderError):
    pass


class ProviderConfigError(ProviderError):
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when a provider is temporarily unavailable."""
    pass


class BaseClient(ABC):
    provider: str
    model: str
    mode: str

    @abstractmethod
    def draft(self, prompt: str, max_tokens: int, temperature: float, timeout: float) -> DraftResult:  # pragma: no cover - interface
        ...

    @abstractmethod
    def suggest_edits(self, prompt: str, timeout: float) -> SuggestResult:  # pragma: no cover - interface
        ...

    @abstractmethod
    def qa_recheck(self, prompt: str, timeout: float) -> QAResult:  # pragma: no cover - interface
        ...
