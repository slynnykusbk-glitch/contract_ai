from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)


def test_analyze_minimal():
    resp = client.post(
        "/api/analyze",
        json={"text": "Hello"},
        headers={"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION},
    )
    assert resp.status_code == 200
    assert resp.headers["x-schema-version"] == SCHEMA_VERSION
    assert resp.headers.get("x-cid")
    data = resp.json()
    assert isinstance(data.get("analysis"), dict) and data["analysis"]


@settings(deadline=None, max_examples=25)
@given(st.text(min_size=1, max_size=100))
def test_analyze_any_text(text):
    resp = client.post(
        "/api/analyze",
        json={"text": text},
        headers={"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION},
    )
    assert resp.status_code == 200
    assert resp.headers.get("x-cid")
