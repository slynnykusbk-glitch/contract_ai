from __future__ import annotations

import httpx

from ..config import LLMConfig
from ..interfaces import (
    BaseClient,
    DraftResult,
    QAResult,
    SuggestResult,
    ProviderTimeoutError,
    ProviderAuthError,
    ProviderConfigError,
)


class ProviderUnavailableError(Exception):
    def __init__(self, provider: str, detail: str):
        super().__init__(detail)
        self.provider = provider
        self.detail = detail


class AnthropicClient(BaseClient):
    def __init__(self, cfg: LLMConfig):
        self.provider = "anthropic"
        self.mode = "live"
        self.model = cfg.model_draft
        self._api_key = cfg.anthropic_api_key or ""
        self._base = cfg.anthropic_base.rstrip("/")
        self._version = "2023-06-01"

    def _post(self, payload: dict, timeout: float) -> dict:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._version,
        }
        try:
            r = httpx.post(
                f"{self._base}/messages", json=payload, headers=headers, timeout=timeout
            )
        except httpx.TimeoutException:
            raise ProviderTimeoutError(self.provider, timeout)
        if r.status_code in (401, 403):
            raise ProviderAuthError(self.provider, r.text)
        if r.status_code >= 400:
            raise ProviderConfigError(self.provider, r.text)
        return r.json()

    def draft(
        self, prompt: str, max_tokens: int, temperature: float, timeout: float
    ) -> DraftResult:
        data = self._post(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout,
        )
        text = data.get("content", [{}])[0].get("text", "")
        usage = data.get("usage") or {}
        return DraftResult(
            text=text,
            meta={
                "provider": self.provider,
                "model": self.model,
                "mode": self.mode,
                "usage": usage,
            },
        )

    def suggest_edits(self, prompt: str, timeout: float) -> SuggestResult:
        data = self._post(
            {"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            timeout,
        )
        text = data.get("content", [{}])[0].get("text", "")
        usage = data.get("usage") or {}
        items = [{"text": text}]
        return SuggestResult(
            items=items,
            meta={
                "provider": self.provider,
                "model": self.model,
                "mode": self.mode,
                "usage": usage,
            },
        )

    def qa_recheck(self, prompt: str, timeout: float) -> QAResult:
        data = self._post(
            {"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            timeout,
        )
        text = data.get("content", [{}])[0].get("text", "")
        usage = data.get("usage") or {}
        items = [text]
        return QAResult(
            items=items,
            meta={
                "provider": self.provider,
                "model": self.model,
                "mode": self.mode,
                "usage": usage,
            },
        )
