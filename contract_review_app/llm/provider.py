"""Lightweight LLM providers used by API layer tests.

This module intentionally avoids heavy dependencies and implements just enough
functionality for the mock and Azure backed providers.  For the Azure client we
now support a unified environment variable matrix and expose a generic ``chat``
method that is used by both ``/api/gpt-draft`` and ``/api/suggest_edits``
endpoints.
"""

import os
import requests
from typing import Any, Dict, List


class ProviderError(RuntimeError): ...


class MockProvider:
    """Deterministic mock used in tests."""

    name = "mock"
    model = "mock"

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_tokens: int = 1024,
        timeout: int = 30,
        **opts: Any,
    ) -> Dict[str, Any]:
        """Deterministic chat interface for tests."""
        text = "\n".join(m.get("content", "") for m in messages)
        usage = {"total_tokens": len(text.split())}
        return {"content": f"[MOCK] {text}", "usage": usage}

    # Backwards compatibility helpers
    def draft(self, prompt: str) -> Dict[str, Any]:
        res = self.chat([{"role": "user", "content": prompt}])
        return {"text": res["content"], "usage": res["usage"]}

    def suggest(self, text: str) -> Dict[str, Any]:
        res = self.chat([{"role": "user", "content": text}])
        return {"proposed_text": res["content"], "usage": res["usage"]}

    def ping(self):
        return {"ok": True}


class AzureProvider:
    def __init__(self):
        ep = os.getenv("AZURE_OPENAI_ENDPOINT")
        dep = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        ver = os.getenv("AZURE_OPENAI_API_VERSION")
        key = (
            os.getenv("AZURE_OPENAI_KEY")
            or os.getenv("AZURE_OPENAI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        if not (ep and dep and ver and key):
            raise ProviderError("Azure env is incomplete")
        self.endpoint = ep.rstrip("/")
        self.deployment = dep
        self.api_version = ver
        self.key = key
        self.name = "azure"
        self.model = dep
        # for trace diagnostics we expose first characters only
        self.endpoint_hint = self.endpoint[:2]
        self.deployment_hint = self.deployment[:2]

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_tokens: int = 1024,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"
        r = requests.post(
            f"{url}?api-version={self.api_version}",
            headers={"api-key": self.key, "Content-Type": "application/json"},
            json={
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        if not r.ok:
            raise ProviderError(f"Azure HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage") or {}
        return {"content": content, "usage": usage}

    def draft(self, prompt: str) -> Dict[str, Any]:  # backwards compat
        res = self.chat(
            [{"role": "user", "content": f"Draft a concise clause revision:\n{prompt}"}]
        )
        return {"text": res["content"], "usage": res["usage"]}

    def suggest(self, text: str) -> Dict[str, Any]:
        res = self.chat(
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
        return {"proposed_text": res["content"], "usage": res["usage"]}

    def ping(self):
        # minimal 1-token chat; 5s timeout
        import time

        t0 = time.perf_counter()
        _ = self.chat(
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
    want = (os.getenv("LLM_PROVIDER") or "").lower()
    if want in {"", "mock"}:
        return MockProvider()
    if want == "azure":
        return AzureProvider()
    raise ProviderError(f"Unsupported LLM_PROVIDER: {want}")
