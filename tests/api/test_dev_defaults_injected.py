import os
from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def test_dev_defaults_injected_when_missing(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("DEFAULT_API_KEY", "secret")
    client = TestClient(app)
    resp = client.post("/api/analyze", json={"text": "hi"})
    assert resp.status_code == 200
    assert resp.headers.get("x-schema-version") == SCHEMA_VERSION


def test_prod_missing_api_key_401(monkeypatch):
    monkeypatch.delenv("DEV_MODE", raising=False)
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("API_KEY", "secret")
    client = TestClient(app)
    resp = client.post("/api/analyze", json={"text": "hi"})
    assert resp.status_code == 401


def test_no_scope_header_mutation(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "1")
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
