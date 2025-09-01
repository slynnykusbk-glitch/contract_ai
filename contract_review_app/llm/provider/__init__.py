"""Provider utilities for Contract Review App.

This package exposes the legacy ``LLMProvider`` abstraction used by the
orchestrator as well as the lightweight draft helpers.  The latter are selected
via :func:`provider_from_env` and power the ``/api/gpt-draft`` endpoint.
"""

from .base import LLMConfig, LLMResult, LLMProvider
from .mock_provider import MockProvider
from .proxy import ProxyProvider
from .draft import DraftResult, provider_from_env

__all__ = [
    "LLMConfig",
    "LLMResult",
    "LLMProvider",
    "MockProvider",
    "ProxyProvider",
    "DraftResult",
    "provider_from_env",
]
