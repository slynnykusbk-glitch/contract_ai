import os
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


client = TestClient(app)


def test_get_health_without_headers():
    assert client.get("/api/health").status_code == 200


def test_post_analyze_missing_api_key():
    r = client.post("/api/analyze", json={"text": "hi"})
    assert r.status_code == 401
    assert r.json() == {"detail": "missing x-api-key"}


def test_post_analyze_missing_schema():
    r = client.post(
        "/api/analyze", json={"text": "hi"}, headers={"x-api-key": "k"}
    )
    assert r.status_code == 400
    assert r.json() == {"detail": "missing x-schema-version"}


def test_post_analyze_ok_headers():
    headers = {"x-api-key": "k", "x-schema-version": SCHEMA_VERSION}
    r = client.post("/api/analyze", json={"text": "hi"}, headers=headers)
    assert r.status_code == 200
    assert r.headers["x-schema-version"] == SCHEMA_VERSION
    assert r.headers.get("X-Cid")
