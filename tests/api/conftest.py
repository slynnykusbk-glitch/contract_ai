import os

import pytest
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


@pytest.fixture(autouse=True)
def ensure_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    yield


@pytest.fixture
def api():
    return TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})


@pytest.fixture
def sample_cid(api):
    r = api.post("/api/analyze", json={"text": "Hello"})
    assert r.status_code == 200
    cid = r.headers.get("x-cid")
    assert cid
    return cid


@pytest.fixture
def analyzed_doc(api):
    r = api.post("/api/analyze", json={"text": "Hello"})
    assert r.status_code == 200
    data = r.json()
    data["cid"] = r.headers.get("x-cid")
    return data
