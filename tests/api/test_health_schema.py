from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def test_health_schema():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert resp.headers.get("x-schema-version") == SCHEMA_VERSION
    assert data.get("schema") == SCHEMA_VERSION
    assert isinstance(data.get("rules_count"), int) and data["rules_count"] >= 1
