from __future__ import annotations

from string import Formatter
from typing import Any, Dict, Optional, Set

from contract_review_app.api.limits import LLM_TIMEOUT_S

from .config import LLMConfig, load_llm_config
from .interfaces import (
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderAuthError,
    ProviderConfigError,
    BaseClient,
    DraftResult,
    SuggestResult,
    QAResult,
)
from .clients.mock_client import MockClient


def _normalize_rules_ctx(rules_ctx):
    if rules_ctx is None:
        return {"rules": []}
    if isinstance(rules_ctx, list):
        return {"rules": rules_ctx}
    return rules_ctx


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
    return MockClient(cfg.model_draft)


class LLMService:
    def __init__(self, cfg: Optional[LLMConfig] = None):
        self.cfg = cfg or load_llm_config()
        self.client: BaseClient = get_client(self.cfg.provider, self.cfg)

    # prompt loading helpers
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
        to = timeout or self.cfg.timeout_s or LLM_TIMEOUT_S
        return self.client.draft(prompt, max_t, temp, to)

    def suggest(
        self, text: str, risk_level: str, timeout: Optional[float] = None
    ) -> SuggestResult:
        prompt_tpl = self._read_prompt("suggest")
        prompt = prompt_tpl.format(text=text, risk=risk_level)
        to = timeout or self.cfg.timeout_s or LLM_TIMEOUT_S
        return self.client.suggest_edits(prompt, to)

    def _safe_format_prompt(self, tpl: str, **kw: Any) -> str:
        formatter = Formatter()
        fields: Set[str] = {fname for _, fname, _, _ in formatter.parse(tpl) if fname}
        allowed = {"text", "rules"}
        unknown = fields - allowed
        if unknown:
            raise ValueError(
                f"qa_prompt_invalid: unknown placeholders={','.join(sorted(unknown))}"
            )
        return tpl.format(**{k: kw.get(k, "") for k in allowed})

    def qa(
        self,
        text: str,
        rules_context=None,
        timeout_s: float = 30,
        profile: str = "vanilla",
    ) -> QAResult:
        rules_context = _normalize_rules_ctx(rules_context)
        if profile == "smart" and not rules_context:
            raise ValueError("qa_prompt_invalid: missing rules context")
        prompt_tpl = self._read_prompt("qa")
        safe_rules = []
        for r in rules_context.get("rules", []):
            safe_rules.append(
                {
                    "id": str(r.get("id", "")),
                    "status": str(r.get("status", "")).lower(),
                    "note": r.get("note", ""),
                }
            )
        rules_ctx = {"rules": safe_rules}
        prompt = self._safe_format_prompt(prompt_tpl, text=text, rules=rules_ctx)
        to = timeout_s or self.cfg.timeout_s or LLM_TIMEOUT_S
        result = self.client.qa_recheck(prompt, to)
        result.meta["profile"] = profile
        return result


def create_llm_service() -> LLMService:
    cfg = load_llm_config()
    return LLMService(cfg)


__all__ = [
    "LLMService",
    "load_llm_config",
    "create_llm_service",
    "ProviderError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "ProviderAuthError",
    "ProviderConfigError",
    "BaseClient",
    "DraftResult",
    "SuggestResult",
    "QAResult",
]
