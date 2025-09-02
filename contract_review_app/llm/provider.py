from __future__ import annotations

import os
import requests
from typing import Dict, Any


class ProviderError(RuntimeError): ...


class MockProvider:
    name = "mock"
    model = "mock"

    def draft(self, prompt: str) -> Dict[str, Any]:
        return {"text": f"[MOCK DRAFT]\n{prompt}"}

    def suggest(self, text: str) -> Dict[str, Any]:
        # trivial, deterministic
        return {
            "proposed_text": text.replace("Confidential", "Confidential (as defined)")
        }

    def ping(self):
        return {"ok": True}


class AzureProvider:
    def __init__(self):
        ep = os.getenv("AZURE_OPENAI_ENDPOINT")
        dep = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        ver = os.getenv("AZURE_OPENAI_API_VERSION")
        key = os.getenv("AZURE_OPENAI_API_KEY")
        if not (ep and dep and ver and key):
            raise ProviderError("Azure env is incomplete")
        self.endpoint = ep.rstrip("/")
        self.deployment = dep
        self.api_version = ver
        self.key = key
        self.name = "azure"
        self.model = dep

    def _chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout: int = 30,
    ):
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"
        r = requests.post(
            f"{url}?api-version={self.api_version}",
            headers={"api-key": self.key, "Content-Type": "application/json"},
            json={
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        if not r.ok:
            raise ProviderError(f"Azure HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        return data["choices"][0]["message"]["content"]

    def draft(self, prompt: str) -> Dict[str, Any]:
        out = self._chat(
            [{"role": "user", "content": f"Draft a concise clause revision:\n{prompt}"}]
        )
        return {"text": out}

    def suggest(self, text: str) -> Dict[str, Any]:
        out = self._chat(
            [
                {
                    "role": "system",
                    "content": "You are a contract drafting assistant. Return only the revised clause.",
                },
                {
                    "role": "user",
                    "content": f"Revise the following for clarity and compliance, keep structure:\n{text}",
                },
            ]
        )
        return {"proposed_text": out}

    def ping(self):
        # minimal 1-token chat; 5s timeout
        import time

        t0 = time.perf_counter()
        _ = self._chat(
            [{"role": "user", "content": "Reply with: pong"}],
            temperature=0.0,
            max_tokens=1,
            timeout=5,
        )
        dt = int((time.perf_counter() - t0) * 1000)
        return {"ok": True, "latency_ms": dt}


def get_provider():
    # explicit selector; env var wins
    # hint for local runs: set LLM_PROVIDER=azure
    want = (os.getenv("LLM_PROVIDER") or os.getenv("AI_PROVIDER") or "").lower()
    if want == "azure":
        try:
            return AzureProvider()
        except ProviderError:
            # fall through to mock if misconfigured
            return MockProvider()
    return MockProvider()
