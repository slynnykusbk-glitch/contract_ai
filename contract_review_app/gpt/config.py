from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

from contract_review_app.api.limits import LLM_TIMEOUT_S

try:  # pragma: no cover - best effort
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional dependency
    pass


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
    log = logging.getLogger("contract_ai")
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"
    if provider not in ALLOWED_PROVIDERS:
        provider = "mock"

    cfg = LLMConfig(provider=provider)

    # generic defaults
    cfg.timeout_s = LLM_TIMEOUT_S
    cfg.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "800"))
    cfg.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    key = ""
    if provider == "azure":
        key = (
            os.getenv("AZURE_OPENAI_KEY")
            or os.getenv("AZURE_OPENAI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        ).strip()
        cfg.azure_api_key = key or None
        cfg.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or None
        cfg.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION") or None
        cfg.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or None
        default_model = cfg.azure_deployment or ""
        cfg.model_draft = os.getenv("MODEL_DRAFT") or default_model
        cfg.model_suggest = os.getenv("MODEL_SUGGEST") or cfg.model_draft
        cfg.model_qa = os.getenv("MODEL_QA") or cfg.model_draft
        required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_VERSION"]
        if not key:
            required.append("AZURE_OPENAI_KEY")
    else:  # mock
        default_model = "mock-static"
        cfg.model_draft = os.getenv("MODEL_DRAFT") or default_model
        cfg.model_suggest = os.getenv("MODEL_SUGGEST") or cfg.model_draft
        cfg.model_qa = os.getenv("MODEL_QA") or cfg.model_draft
        required = []

    missing = [name for name in required if not os.getenv(name)]
    cfg.missing = missing

    invalid_key = False
    if provider == "azure":
        if not key or key in {"*", "changeme"} or len(key) < 24:
            invalid_key = True
    cfg.valid = (provider == "mock") or (not missing and not invalid_key)
    if provider == "mock":
        cfg.mode = "mock"
    elif cfg.valid:
        cfg.mode = "live"
    else:
        cfg.mode = "mock-or-error"

    masked = (key[:4] + "***") if key else ""
    log.info(
        "LLM config: provider=%s model_draft=%s model_suggest=%s model_qa=%s endpoint=%s api_version=%s key=%s valid=%s",
        cfg.provider,
        cfg.model_draft,
        cfg.model_suggest,
        cfg.model_qa,
        cfg.azure_endpoint or "",
        cfg.azure_api_version or "",
        masked,
        cfg.valid,
    )
    return cfg
