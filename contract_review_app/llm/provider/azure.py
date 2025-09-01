import os, difflib, httpx
from .base import LLMProvider, DraftResult

class AzureProvider(LLMProvider):
    def __init__(self) -> None:
        self.endpoint   = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.api_ver    = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        self.api_key    = os.environ["AZURE_OPENAI_API_KEY"]
        self._model_hint = os.getenv("AZURE_OPENAI_MODEL", "")

    def _ask(self, prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> dict:
        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions"
        params = {"api-version": self.api_ver}
        body = {
            "messages": [
                {"role": "system",
                 "content": "You are a contracts assistant. Return only the improved clause text."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"api-key": self.api_key}
        with httpx.Client(timeout=60.0) as cli:
            r = cli.post(url, params=params, headers=headers, json=body)
            r.raise_for_status()
            return r.json()

    def draft(self, text: str, mode: str = "friendly") -> DraftResult:
        style = {
            "friendly": "mild and businesslike",
            "medium":   "balanced and precise",
            "strict":   "firm and risk-averse",
        }.get(mode, "balanced and precise")

        prompt = (
            "Rewrite/improve the following NDA clause to be clearer and compliant with UK practice. "
            f"Tone: {style}. Keep semantics. Output final clause text only.\n\nCLAUSE:\n{text}"
        )
        j = self._ask(prompt)
        after = j["choices"][0]["message"]["content"]
        diff = "\n".join(difflib.unified_diff((text or '').splitlines(), after.splitlines(), lineterm=""))
        usage = j.get("usage") or {}
        return DraftResult(
            proposed_text=after,
            rationale=f"Improved clarity and compliance (mode={mode}).",
            evidence=[],
            before_text=text or "",
            after_text=after,
            diff_unified=diff,
            provider="azure",
            model=self._model_hint or str(j.get("model") or ""),
            mode=mode,
            usage=usage if isinstance(usage, dict) else {},
        )
