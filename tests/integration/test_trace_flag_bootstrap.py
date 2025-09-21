import importlib
import os
import sys
from typing import Tuple

from fastapi.testclient import TestClient

from contract_review_app.api.models import SCHEMA_VERSION


_TRACE_KEYS = ("features", "dispatch", "constraints", "proposals")


def _headers() -> dict[str, str]:
    return {"x-api-key": "dummy", "x-schema-version": SCHEMA_VERSION}


def _build_client(flag: str) -> Tuple[TestClient, list[str]]:
    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
    ]
    for name in modules:
        sys.modules.pop(name, None)
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["FEATURE_TRACE_ARTIFACTS"] = flag
    from contract_review_app.api import app as app_module

    importlib.reload(app_module)

    def fake_analyze(text: str):
        return {
            "analysis": {"issues": ["dummy"]},
            "results": {},
            "clauses": [],
            "document": {"text": text},
        }

    app_module._analyze_document = fake_analyze
    client = TestClient(app_module.app)
    return client, modules


def _cleanup(client: TestClient, modules: list[str]) -> None:
    try:
        client.close()
    finally:
        for name in modules:
            sys.modules.pop(name, None)
        os.environ.pop("LLM_PROVIDER", None)
        os.environ.pop("FEATURE_TRACE_ARTIFACTS", None)


def test_trace_flag_disabled():
    client, modules = _build_client("0")
    try:
        response = client.post(
            "/api/analyze", headers=_headers(), json={"text": "Hi"}
        )
        assert response.status_code == 200
        cid = response.headers.get("x-cid")
        assert cid
        trace = client.get(f"/api/trace/{cid}")
        assert trace.status_code == 200
        payload = trace.json()
        for key in _TRACE_KEYS:
            assert key not in payload
    finally:
        _cleanup(client, modules)


def test_trace_flag_enabled():
    client, modules = _build_client("1")
    try:
        response = client.post(
            "/api/analyze", headers=_headers(), json={"text": "Hi"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        cid = response.headers.get("x-cid")
        assert cid
        trace = client.get(f"/api/trace/{cid}")
        assert trace.status_code == 200
        payload = trace.json()
        for key in _TRACE_KEYS:
            assert key in payload
            assert payload[key] == {}
    finally:
        _cleanup(client, modules)
