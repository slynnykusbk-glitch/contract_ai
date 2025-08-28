import pytest

from contract_review_app.llm.provider.proxy import ProxyProvider
from contract_review_app.llm.provider import LLMConfig, MockProvider


def test_default_env_uses_mock(monkeypatch):
    monkeypatch.delenv("CONTRACTAI_LLM_PROVIDERS", raising=False)
    proxy = ProxyProvider()
    assert proxy.providers_order == ["mock"]
    cfg = LLMConfig()
    res1 = proxy.generate("hello", cfg)
    res2 = proxy.generate("hello", cfg)
    assert res1.text == "MOCK:hello"
    assert res1 == res2
    assert res1.provider == "mock"


def test_fallback_to_mock(monkeypatch):
    monkeypatch.setenv("CONTRACTAI_LLM_PROVIDERS", "openai,mock")
    proxy = ProxyProvider()
    cfg = LLMConfig()
    res = proxy.generate("hi", cfg)
    assert res.provider == "mock"
    assert res.text.startswith("MOCK:")


def test_max_retries(monkeypatch):
    monkeypatch.setenv("CONTRACTAI_LLM_PROVIDERS", "mock")
    monkeypatch.setenv("CONTRACTAI_LLM_MAX_RETRIES", "1")
    calls = {"count": 0}

    def boom(self, prompt, config):
        calls["count"] += 1
        raise ValueError("boom")

    monkeypatch.setattr(MockProvider, "generate", boom, raising=False)
    proxy = ProxyProvider()
    with pytest.raises(ValueError):
        proxy.generate("x", LLMConfig())
    assert calls["count"] == 1


def test_no_providers(monkeypatch):
    monkeypatch.setenv("CONTRACTAI_LLM_PROVIDERS", "")
    proxy = ProxyProvider()
    with pytest.raises(RuntimeError):
        proxy.generate("x", LLMConfig())


def test_determinism(monkeypatch):
    monkeypatch.delenv("CONTRACTAI_LLM_PROVIDERS", raising=False)
    proxy = ProxyProvider()
    cfg = LLMConfig()
    out1 = proxy.generate("foo", cfg)
    out2 = proxy.generate("foo", cfg)
    assert out1 == out2
