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


class AzureClient(BaseClient):
    def __init__(self, cfg: LLMConfig):
        self.provider = "azure"
        self.mode = "live"
        self.model = cfg.model_draft or (cfg.azure_deployment or "")
        self._api_key = cfg.azure_api_key or ""
        self._endpoint = (cfg.azure_endpoint or "").rstrip("/")
        self._deployment = cfg.azure_deployment or self.model
        self._api_version = cfg.azure_api_version or "2024-02-15"

    def _post(self, payload: dict, timeout: float) -> dict:
        url = f"{self._endpoint}/openai/deployments/{self._deployment}/chat/completions?api-version={self._api_version}"
        headers = {"api-key": self._api_key}
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=timeout)
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
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
