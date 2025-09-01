import os
import requests
import difflib
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class DraftResult:
    proposed_text: str
    rationale: str
    evidence: List[Dict]
    before_text: str
    after_text: str
    diff_unified: str


class LLMProviderBase:
    def draft(self, text: str, mode: str = "friendly") -> DraftResult:
        raise NotImplementedError()


class MockProvider(LLMProviderBase):
    def draft(self, text: str, mode: str = "friendly") -> DraftResult:
        before = (text or "").strip()
        after = before + ("\n\n[Mock suggestion: tighten confidentiality carve-outs.]")
        diff = "\n".join(
            difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="")
        )
        return DraftResult(
            proposed_text=after,
            rationale="Mock rationale.",
            evidence=[],
            before_text=before,
            after_text=after,
            diff_unified=diff,
        )


class AzureProvider(LLMProviderBase):
    def __init__(self):
        self.endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.api_ver = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        self.api_key = os.environ["AZURE_OPENAI_API_KEY"]

    def _ask(self, prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> str:
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_ver}"
        body = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a contracts assistant. Return only the improved clause text. No commentary.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, headers={"api-key": self.api_key}, json=body, timeout=60)
        r.raise_for_status()
        j = r.json()
        return j["choices"][0]["message"]["content"]

    def draft(self, text: str, mode: str = "friendly") -> DraftResult:
        before = (text or "").strip()
        style = {
            "friendly": "mild and businesslike",
            "medium": "balanced and precise",
            "strict": "firm and risk-averse",
        }.get(mode, "balanced and precise")

        prompt = (
            "Rewrite/improve the following NDA clause to be clearer and compliant with UK practice. "
            f"Tone: {style}. Keep semantics. Output only the final clause text (no preamble).\n\n"
            f"CLAUSE:\n{before}"
        )
        after = self._ask(prompt)
        diff = "\n".join(
            difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="")
        )
        return DraftResult(
            proposed_text=after,
            rationale=f"Improved clarity and compliance (mode={mode}).",
            evidence=[],
            before_text=before,
            after_text=after,
            diff_unified=diff,
        )


def get_provider():
    provider = os.environ.get("CONTRACTAI_PROVIDER", "mock").lower()
    if provider == "azure":
        return AzureProvider()
    return MockProvider()
