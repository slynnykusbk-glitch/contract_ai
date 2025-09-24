import pytest
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION


client = TestClient(app)


def _headers() -> dict[str, str]:
    return {"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"text": "Legacy"}, id="top-level-text"),
        pytest.param(
            {"payload": {"text": "Nested clause content for draft."}},
            id="nested-payload-text",
        ),
        pytest.param(
            {"clause": "Clause coming from legacy clients."}, id="clause-field"
        ),
    ],
)
def test_gpt_draft_alias_accepts_legacy_payloads(payload):
    resp = client.post("/api/gpt-draft", json=payload, headers=_headers())
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["schema"] == SCHEMA_VERSION
    assert data["draft_text"].strip()
    assert data["draft_text"].startswith("Draft:")


def test_gpt_draft_alias_preserves_original_text_when_present():
    payload = {"text": "   Some clause from legacy payload   "}
    resp = client.post("/api/gpt-draft", json=payload, headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_text"].strip().startswith("Some clause")
