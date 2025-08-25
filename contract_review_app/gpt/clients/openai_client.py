from __future__ import annotations

import requests

from ..config import LLMConfig
from ..service import (
    BaseClient,
    DraftResult,
    QAResult,
    SuggestResult,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class OpenAIClient(BaseClient):
    def __init__(self, cfg: LLMConfig):
        self.provider = "openai"
        self.model = cfg.model_draft
        self.mode = "live"
        self._api_key = cfg.openai_api_key or ""
        self._base = cfg.openai_base.rstrip("/")

    def _post(self, payload: dict, timeout: float) -> dict:
        try:
            r = requests.post(
                f"{self._base}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=timeout,
            )
        except requests.Timeout:
            raise ProviderTimeoutError(self.provider, timeout)
        if r.status_code >= 400:
            raise ProviderUnavailableError(self.provider, r.text)
        return r.json()

    def generate_draft(self, prompt: str, max_tokens: int, temperature: float, timeout: float) -> DraftResult:
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
        return DraftResult(text=text, meta={"provider": self.provider, "model": self.model, "mode": self.mode, "usage": usage})

    def suggest_edits(self, prompt: str, timeout: float) -> SuggestResult:
        data = self._post({"model": self.model, "messages": [{"role": "user", "content": prompt}]}, timeout)
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage") or {}
        items = [{"text": text}]
        return SuggestResult(items=items, meta={"provider": self.provider, "model": self.model, "mode": self.mode, "usage": usage})

    def qa_recheck(self, prompt: str, timeout: float) -> QAResult:
        data = self._post({"model": self.model, "messages": [{"role": "user", "content": prompt}]}, timeout)
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage") or {}
        items = [text]
        return QAResult(items=items, meta={"provider": self.provider, "model": self.model, "mode": self.mode, "usage": usage})
