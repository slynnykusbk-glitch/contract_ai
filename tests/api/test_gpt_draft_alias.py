from fastapi import FastAPI
from fastapi.testclient import TestClient
from contract_review_app.gpt.gpt_draft_api import router, SCHEMA_VERSION


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_gpt_draft_alias_returns_same_response():
    payload = {"analysis": {"text": "T", "citations": []}}
    r1 = client.post("/api/gpt-draft", json=payload)
    r2 = client.post("/api/gpt/draft", json=payload)
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert r1.headers["x-schema-version"] == SCHEMA_VERSION == r2.headers["x-schema-version"]
    assert r1.json()["schema"] == SCHEMA_VERSION
