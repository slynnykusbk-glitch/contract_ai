"""Light‑weight provider implementations used by the gpt-draft endpoint.

The historic codebase shipped a slightly different provider abstraction that
exposed a ``generate`` method.  For the panel draft functionality we only need
to support a very small surface area – a provider that can turn an arbitrary
piece of text into a draft clause.  The :func:`draft` method implemented by the
providers below returns a :class:`DraftResult` which contains all data required
by the front‑end (proposed text, rationale, etc.).

The module also exposes :func:`provider_from_env` which instantiates the
appropriate provider based on the ``CONTRACTAI_PROVIDER`` environment variable.
In CI and tests the default is a deterministic mock provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import difflib
import os
from typing import Any, Dict, List


@dataclass
class DraftResult:
    """Result returned by :class:`AzureProvider` and :class:`MockProvider`."""

    proposed_text: str
    rationale: str
    evidence: List[str]
    before_text: str
    after_text: str
    mode: str
    provider: str
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)

    @property
    def diff_unified(self) -> str:
        """Return unified diff between ``before_text`` and ``after_text``."""
        return "\n".join(
            difflib.unified_diff(
                (self.before_text or "").splitlines(),
                (self.after_text or "").splitlines(),
                lineterm="",
            )
        )


class MockProvider:
    """Deterministic provider used in development and tests."""

    provider = "mock"
    model = "mock-draft"

    def draft(self, text: str, mode: str) -> DraftResult:
        base = text or ""
        draft = f"{base} [{mode} draft]".strip()
        rationale = f"mock rationale ({mode})"
        return DraftResult(
            proposed_text=draft,
            rationale=rationale,
            evidence=[],
            before_text=base,
            after_text=draft,
            mode=mode,
            provider=self.provider,
            model=self.model,
        )


class AzureProvider:
    """Minimal Azure OpenAI provider.

    The implementation intentionally keeps dependencies light; if the required
    credentials are not configured the provider gracefully falls back to
    returning the original text.
    """

    provider = "azure"

    def __init__(self) -> None:
        self.model = os.getenv("AZURE_OPENAI_MODEL", os.getenv("AZURE_OPENAI_DEPLOYMENT", ""))
        self._endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/")
        self._api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self._deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", self.model)
        self._api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15")

    def draft(self, text: str, mode: str) -> DraftResult:
        if not self._endpoint or not self._api_key:
            # Environment not configured – behave similar to the mock provider
            draft = text or ""
            return DraftResult(
                proposed_text=draft,
                rationale="azure provider not configured",
                evidence=[],
                before_text=text or "",
                after_text=draft,
                mode=mode,
                provider=self.provider,
                model=self.model,
            )

        url = (
            f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions"
            f"?api-version={self._api_version}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": f"Rewrite the following text in a {mode} tone.",
                },
                {"role": "user", "content": text},
            ],
        }
        headers = {"api-key": self._api_key}

        try:
            import requests  # lazily import to keep mock default lightweight

            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            data = resp.json()
            draft = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            usage = data.get("usage") or {}
        except Exception:
            draft = text or ""
            usage = {}

        return DraftResult(
            proposed_text=draft,
            rationale="",
            evidence=[],
            before_text=text or "",
            after_text=draft,
            mode=mode,
            provider=self.provider,
            model=self.model,
            usage=usage,
        )


def provider_from_env() -> MockProvider | AzureProvider:
    """Return provider instance based on ``CONTRACTAI_PROVIDER`` env var."""

    name = os.getenv("CONTRACTAI_PROVIDER", "mock").strip().lower()
    if name == "azure":
        return AzureProvider()
    return MockProvider()


__all__ = ["DraftResult", "provider_from_env"]

