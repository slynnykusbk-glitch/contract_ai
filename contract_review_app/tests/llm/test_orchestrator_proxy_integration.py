import pytest

from contract_review_app.llm.orchestrator import Orchestrator
from contract_review_app.llm.provider.proxy import ProxyProvider


def test_orchestrator_uses_proxy(monkeypatch):
    monkeypatch.delenv("CONTRACTAI_LLM_PROVIDERS", raising=False)
    orch = Orchestrator()
    assert isinstance(orch.provider, ProxyProvider)
    res_draft = orch.draft("Q", "C")
    res_suggest = orch.suggest_edits("Q", "C")
    for res in (res_draft, res_suggest):
        assert res.provider == "mock"
        assert "MOCK:" in res.text


def test_orchestrator_no_fallback(monkeypatch):
    monkeypatch.setenv("CONTRACTAI_LLM_PROVIDERS", "openai")
    orch = Orchestrator()
    with pytest.raises(NotImplementedError):
        orch.draft("Q", "C")


def test_orchestrator_fallback(monkeypatch):
    monkeypatch.setenv("CONTRACTAI_LLM_PROVIDERS", "openai,mock")
    orch = Orchestrator()
    res = orch.draft("Q", "C")
    assert res.provider == "mock"
    assert res.text.startswith("MOCK:")
