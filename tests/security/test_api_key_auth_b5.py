from fastapi.testclient import TestClient
from contract_review_app.api import app as app_module
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app_module.app)


def test_api_key_required():
    r = client.post("/api/analyze", json={"text": "hi"})
    assert r.status_code == 401

    r = client.post(
        "/api/analyze",
        json={"text": "hi"},
        headers={"x-api-key": "secret", "x-schema-version": SCHEMA_VERSION},
    )
    assert r.status_code == 200
