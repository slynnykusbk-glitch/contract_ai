import os
from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def test_missing_api_key_401(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY","1")
    with TestClient(app) as c:
        r = c.post("/api/analyze", json={"text":"Hi"}, headers={"x-schema-version":SCHEMA_VERSION})
        assert r.status_code == 401


def test_missing_schema_version_400(monkeypatch):
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY","1"); monkeypatch.setenv("API_KEY","local-test-key-123")
    with TestClient(app) as c:
        r = c.post("/api/analyze", json={"text":"Hi"}, headers={"x-api-key":"local-test-key-123"})
        assert r.status_code == 400
