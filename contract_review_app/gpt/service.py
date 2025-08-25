from __future__ import annotations

from typing import Any, Dict, Optional

from .config import LLMConfig, load_llm_config
from .interfaces import (
    BaseClient,
    DraftResult,
    SuggestResult,
    QAResult,
    ProviderTimeoutError,
    ProviderAuthError,
    ProviderConfigError,
)


def get_client(provider: str, cfg: LLMConfig) -> BaseClient:
    if provider == "openai" and cfg.valid:
        from .clients.openai_client import OpenAIClient
        return OpenAIClient(cfg)
    if provider == "azure" and cfg.valid:
        from .clients.azure_client import AzureClient
        return AzureClient(cfg)
    if provider == "anthropic" and cfg.valid:
        from .clients.anthropic_client import AnthropicClient
        return AnthropicClient(cfg)
    if provider == "openrouter" and cfg.valid:
        from .clients.openrouter_client import OpenRouterClient
        return OpenRouterClient(cfg)
    from .clients.mock_client import MockClient
    return MockClient(cfg.model_draft)


class LLMService:
    def __init__(self, cfg: Optional[LLMConfig] = None):
        self.cfg = cfg or load_llm_config()
        self.client: BaseClient = get_client(self.cfg.provider, self.cfg)

    def _read_prompt(self, name: str) -> str:
        import pkgutil

        data = pkgutil.get_data("contract_review_app.gpt", f"prompts/{name}.txt")
        if not data:
            return ""
        return data.decode("utf-8")

    def draft(
        self,
        text: str,
        clause_type: Optional[str],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
    ) -> DraftResult:
        prompt_tpl = self._read_prompt("draft")
        prompt = prompt_tpl.format(
            clause_type=clause_type or "clause",
            style="formal",
            jurisdiction="UK",
            text=text,
        )
        max_t = max_tokens or self.cfg.max_tokens
        temp = temperature if temperature is not None else self.cfg.temperature
        to = timeout or self.cfg.timeout_s
        return self.client.draft(prompt, max_t, temp, to)

    def suggest(self, text: str, risk_level: str, timeout: Optional[float] = None) -> SuggestResult:
        prompt_tpl = self._read_prompt("suggest")
        prompt = prompt_tpl.format(text=text, risk=risk_level)
        to = timeout or self.cfg.timeout_s
        return self.client.suggest_edits(prompt, to)

    def qa(self, text: str, rules_context: Dict[str, Any], timeout: Optional[float] = None) -> QAResult:
        prompt_tpl = self._read_prompt("qa")
        prompt = prompt_tpl.format(text=text, rules=rules_context)
        to = timeout or self.cfg.timeout_s
        return self.client.qa_recheck(prompt, to)


def create_llm_service() -> LLMService:
    cfg = load_llm_config()
    return LLMService(cfg)
