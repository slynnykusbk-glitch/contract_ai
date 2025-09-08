import pytest
from contract_review_app.llm.provider import get_provider, ProviderError


def test_missing_azure_env_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    # Ensure required Azure variables are not set
    for var in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT",
    ):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ProviderError) as exc:
        get_provider()
    expected = (
        "Azure env vars missing: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, "
        "AZURE_OPENAI_API_VERSION, AZURE_OPENAI_API_KEY"
    )
    assert str(exc.value) == expected
