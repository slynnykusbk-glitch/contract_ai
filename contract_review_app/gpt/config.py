from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


ALLOWED_PROVIDERS = {"azure", "mock"}


@dataclass
class LLMConfig:
    provider: str = "mock"
    model_draft: str = "mock-static"
    model_suggest: str = "mock-static"
    model_qa: str = "mock-static"
    openai_api_key: Optional[str] = None
    openai_base: str = "https://api.openai.com/v1"
    azure_api_key: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_api_version: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_base: str = "https://api.anthropic.com/v1"
    openrouter_api_key: Optional[str] = None
    openrouter_base: str = "https://openrouter.ai/api/v1"
    timeout_s: int = 30
    max_tokens: int = 800
    temperature: float = 0.2
    valid: bool = True
    missing: List[str] = field(default_factory=list)
    mode: str = "mock"  # mock|live|mock-or-error

    def meta(self) -> Dict[str, str]:
        return {"provider": self.provider, "model": self.model_draft, "mode": self.mode}


def load_llm_config() -> LLMConfig:
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"
    if provider not in ALLOWED_PROVIDERS:
        provider = "mock"

    cfg = LLMConfig(provider=provider)

    # generic defaults
    cfg.timeout_s = int(os.getenv("LLM_TIMEOUT_S", "30"))
    cfg.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "800"))
    cfg.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    if provider == "azure":
        cfg.azure_api_key = (
            os.getenv("AZURE_OPENAI_KEY")
            or os.getenv("AZURE_OPENAI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        cfg.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        cfg.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        default_model = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        cfg.model_draft = os.getenv("MODEL_DRAFT", default_model)
        cfg.model_suggest = os.getenv("MODEL_SUGGEST", cfg.model_draft)
        cfg.model_qa = os.getenv("MODEL_QA", cfg.model_draft)
        required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_VERSION"]
        if not cfg.azure_api_key:
            required.append("AZURE_OPENAI_KEY")
    else:  # mock
        default_model = "mock-static"
        cfg.model_draft = os.getenv("MODEL_DRAFT", default_model)
        cfg.model_suggest = os.getenv("MODEL_SUGGEST", cfg.model_draft)
        cfg.model_qa = os.getenv("MODEL_QA", cfg.model_draft)
        required = []

    missing = [name for name in required if not os.getenv(name)]
    cfg.missing = missing
    cfg.valid = (provider == "mock") or not missing
    if provider == "mock":
        cfg.mode = "mock"
    elif cfg.valid:
        cfg.mode = "live"
    else:
        cfg.mode = "mock-or-error"
    return cfg
