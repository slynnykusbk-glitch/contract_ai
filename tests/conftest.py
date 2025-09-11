import pytest
import requests

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("FASTAPI_ENV", "test")
    monkeypatch.setenv("DISABLE_PDF", "1")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    yield


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    orig_req = requests.sessions.Session.request
    if httpx:
        orig_httpx = httpx.Client.request

    def block_requests(self, method, url, *args, **kwargs):
        u = str(url)
        if (
            u.startswith("http://testserver")
            or u.startswith("https://testserver")
            or u.startswith("http://localhost")
            or u.startswith("https://localhost")
            or "api.company-information.service.gov.uk" in u
        ):
            return orig_req(self, method, url, *args, **kwargs)
        raise RuntimeError("External HTTP blocked")

    def block_httpx(self, method, url, *args, **kwargs):
        u = str(url)
        if (
            u.startswith("http://testserver")
            or u.startswith("https://testserver")
            or u.startswith("http://localhost")
            or u.startswith("https://localhost")
            or "api.company-information.service.gov.uk" in u
        ):
            return orig_httpx(self, method, url, *args, **kwargs)
        raise RuntimeError("External HTTP blocked")

    monkeypatch.setattr(requests.sessions.Session, "request", block_requests)
    if httpx:
        monkeypatch.setattr(httpx.Client, "request", block_httpx)
    yield
    monkeypatch.setattr(requests.sessions.Session, "request", orig_req)
    if httpx:
        monkeypatch.setattr(httpx.Client, "request", orig_httpx)
