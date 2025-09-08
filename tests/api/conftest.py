import pytest


@pytest.fixture(autouse=True)
def ensure_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")
    yield
