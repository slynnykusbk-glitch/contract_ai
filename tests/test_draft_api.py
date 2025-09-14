from fastapi.testclient import TestClient
from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

client = TestClient(app)
BASE_HEADERS = {"X-Api-Key": "local-test-key-123", "X-Schema-Version": SCHEMA_VERSION}


def _base_payload():
    return {
        "mode": "friendly",
        "clause": "This clause has more than twenty characters.",
        "context": {"law": "UK", "language": "en-GB", "contractType": "NDA"},
        "findings": [],
        "selection": {"start": 0, "end": 10},
    }


def test_draft_ok():
    r = client.post("/api/gpt/draft", json=_base_payload(), headers=BASE_HEADERS)
    assert r.status_code == 200
    assert r.json()["draft"]


def test_draft_422_empty_clause():
    payload = _base_payload()
    payload["clause"] = ""
    r = client.post("/api/gpt/draft", json=payload, headers=BASE_HEADERS)
    assert r.status_code == 422


def test_draft_422_unknown_field():
    payload = _base_payload()
    payload["extra"] = "boom"
    r = client.post("/api/gpt/draft", json=payload, headers=BASE_HEADERS)
    assert r.status_code == 422
