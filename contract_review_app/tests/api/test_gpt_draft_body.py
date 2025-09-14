import os
from fastapi.testclient import TestClient
import pytest

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)
HEADERS = {"x-api-key": "k", "x-schema-version": SCHEMA_VERSION}


def test_gpt_draft_accepts_text_aliases():
    for payload in (
        {"text": "Ping"},
        {"clause": "Ping"},
        {"payload": {"text": "Ping"}},
    ):
        r = client.post("/api/gpt-draft", json=payload, headers=HEADERS)
        assert r.status_code == 200


@pytest.mark.parametrize("bad_payload", [
    {"text": ""},
    {"clause": " "},
])
def test_gpt_draft_validation_errors(bad_payload):
    r = client.post("/api/gpt-draft", json=bad_payload, headers=HEADERS)
    assert r.status_code == 422
