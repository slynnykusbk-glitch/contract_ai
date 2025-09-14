import logging
import pytest

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from contract_review_app.api.models import SCHEMA_VERSION
from contract_review_app.api.auth import require_api_key_and_schema


def _get_client():
    from contract_review_app.api.app import app

    return TestClient(app)


def test_api_key_auth(monkeypatch):
    monkeypatch.delenv("DEV_MODE", raising=False)
    monkeypatch.delenv("ALLOW_DEV_KEY_INJECTION", raising=False)
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "secret")

    client = _get_client()
    payload = {"text": "Hello"}

    r = client.post("/api/analyze", json=payload)
    assert r.status_code == 401
    r = client.post(
        "/api/gpt-draft", json={"clause_id": "x", "text": "Ping", "mode": "friendly"}
    )
    assert r.status_code == 401
    r = client.post("/api/suggest_edits", json=payload)
    assert r.status_code == 401

    headers = {"x-api-key": "secret", "x-schema-version": SCHEMA_VERSION}
    r_an = client.post("/api/analyze", json=payload, headers=headers)
    assert r_an.status_code == 200
    cid = r_an.headers.get("X-Cid")
    assert (
        client.post(
            "/api/gpt-draft",
            json={"clause_id": cid, "text": "Ping", "mode": "friendly"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post("/api/suggest_edits", json=payload, headers=headers).status_code
        == 200
    )


def _build_request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
    }
    return Request(scope)


def test_dev_key_injection_requires_flag(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.delenv("ALLOW_DEV_KEY_INJECTION", raising=False)

    req = _build_request()
    with pytest.raises(HTTPException) as exc:
        require_api_key_and_schema(req)
    assert exc.value.status_code == 401


def test_dev_key_injection_opt_in(monkeypatch, caplog):
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("ALLOW_DEV_KEY_INJECTION", "yes")
    monkeypatch.setenv("DEFAULT_API_KEY", "local-test-key-123")

    req = _build_request()
    with caplog.at_level(logging.WARNING):
        require_api_key_and_schema(req)
    assert req.state.api_key == "local-test-key-123"
    assert req.state.schema_version == SCHEMA_VERSION
    assert any("auto-filling" in msg for msg in caplog.messages)
