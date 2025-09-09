from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def test_analyze_minimal():
    resp = client.post(
        "/api/analyze",
        json={"text": "Hello", "language": "en"},
        headers={"x-schema-version": SCHEMA_VERSION},
    )
    assert resp.status_code == 200
    assert resp.headers["x-schema-version"] == SCHEMA_VERSION
    data = resp.json()
    assert isinstance(data.get("analysis"), dict) and data["analysis"]
