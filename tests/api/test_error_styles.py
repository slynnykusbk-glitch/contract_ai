from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.errors import UpstreamTimeoutError
from contract_review_app.api.models import SCHEMA_VERSION


@app.get("/__err/validation")
async def _validation_endpoint(v: int):  # pragma: no cover - used in tests only
    return {"v": v}


@app.get("/__err/timeout")
async def _timeout_endpoint():  # pragma: no cover - used in tests only
    raise UpstreamTimeoutError()


@app.get("/__err/boom")
async def _boom_endpoint():  # pragma: no cover - used in tests only
    raise RuntimeError("boom")


client = TestClient(
    app, headers={"x-schema-version": SCHEMA_VERSION}, raise_server_exceptions=False
)


def test_validation_error_style():
    r = client.get("/__err/validation", params={"v": "oops"})
    assert r.status_code == 422
    assert r.json() == {"detail": "validation error"}


def test_timeout_error_style():
    r = client.get("/__err/timeout")
    assert r.status_code == 504
    assert r.json() == {"detail": "upstream timeout"}


def test_internal_error_style():
    r = client.get("/__err/boom")
    assert r.status_code == 500
    assert r.json() == {"detail": "internal error"}
