import importlib
import time

import httpx
import pytest


def test_llm_timeout_respected(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_S", "2")

    from contract_review_app.api import limits as limits_module

    importlib.reload(limits_module)
    from contract_review_app.gpt import config as config_module

    importlib.reload(config_module)
    from contract_review_app.gpt.clients import openai_client
    from contract_review_app.gpt.interfaces import ProviderTimeoutError

    cfg = config_module.LLMConfig()
    cfg.model_draft = "mock"
    cfg.timeout_s = limits_module.LLM_TIMEOUT_S
    cfg.temperature = 0.2
    cfg.max_tokens = 16
    cfg.openai_api_key = "sk-test"
    cfg.openai_base = "https://example.invalid"

    client = openai_client.OpenAIClient(cfg)

    recorded = {}

    def fake_post(url, json, headers, timeout):
        recorded["timeout"] = timeout
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(openai_client.httpx, "post", fake_post)

    start = time.perf_counter()
    with pytest.raises(ProviderTimeoutError):
        client.draft("prompt", cfg.max_tokens, cfg.temperature, cfg.timeout_s)
    duration = time.perf_counter() - start

    assert recorded["timeout"] == limits_module.LLM_TIMEOUT_S
    assert duration <= limits_module.LLM_TIMEOUT_S
