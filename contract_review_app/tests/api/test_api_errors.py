from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import contract_review_app.api.app as app_module
from contract_review_app.api.error_handlers import register_error_handlers
from contract_review_app.api.models import ProblemDetail

client = TestClient(app_module.app, raise_server_exceptions=False)


def test_422_validation_error():
    r = client.post("/api/analyze", json={"text": 123})
    assert r.status_code == 422
    ProblemDetail.model_validate(r.json())
    assert r.json()["status"] == 422


def test_http_exception_problem():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def _boom():
        raise HTTPException(status_code=400, detail="bad")

    tmp = TestClient(app)
    resp = tmp.get("/boom")
    assert resp.status_code == 400
    ProblemDetail.model_validate(resp.json())
    assert resp.json()["status"] == 400


def test_generic_exception(monkeypatch):
    def boom(text: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "_analyze_document", boom, raising=True)
    resp = client.post("/api/analyze", json={"text": "hello"})
    assert resp.status_code == 500
    ProblemDetail.model_validate(resp.json())
    assert "boom" not in resp.text
