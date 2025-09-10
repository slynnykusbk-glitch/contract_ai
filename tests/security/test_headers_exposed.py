from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


def test_health_schema_header():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-schema-version") == SCHEMA_VERSION


def test_cors_expose_headers():
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    headers = {h.lower() for h in cors.kwargs.get("expose_headers", [])}
    for h in ["x-cid", "x-schema-version", "x-provider", "x-model", "x-llm-mode"]:
        assert h in headers
