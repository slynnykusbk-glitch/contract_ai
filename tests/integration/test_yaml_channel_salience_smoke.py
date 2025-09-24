from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _build_client(monkeypatch) -> tuple[TestClient, list[str]]:
    pack_dir = Path(__file__).resolve().parent / "data" / "yaml_smoke_pack"
    monkeypatch.setenv("RULE_PACKS_DIRS", str(pack_dir))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("FEATURE_TRACE_ARTIFACTS", "1")

    modules = [
        "contract_review_app.api",
        "contract_review_app.api.app",
    ]
    for name in modules:
        sys.modules.pop(name, None)

    app_module = importlib.import_module("contract_review_app.api.app")
    client = TestClient(app_module.app)
    return client, modules


def _cleanup(client: TestClient, modules: list[str]) -> None:
    try:
        client.close()
    finally:
        for name in modules:
            sys.modules.pop(name, None)


def test_yaml_channel_salience_smoke(monkeypatch):
    from contract_review_app.api.models import SCHEMA_VERSION

    client, modules = _build_client(monkeypatch)
    try:
        payload = {"text": "This policy channel test should fire our rule."}
        headers = {"x-api-key": "dummy", "x-schema-version": SCHEMA_VERSION}

        response = client.post("/api/analyze", headers=headers, json=payload)
        assert response.status_code == 200

        body = response.json()
        findings = body.get("findings") or []
        assert findings, "expected at least one finding"

        first = findings[0]
        assert first.get("channel") == "policy"
        assert first.get("salience") == 70

        cid = response.headers.get("x-cid") or body.get("cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200

        trace_body = trace_response.json()
        dispatch = trace_body.get("dispatch") or {}
        candidates = dispatch.get("candidates") or []
        assert candidates, "expected dispatch candidates in trace payload"

        rule_id = first.get("rule_id")
        candidate = next(
            (entry for entry in candidates if entry.get("rule_id") == rule_id), None
        )
        assert candidate is not None, "expected matching candidate in trace dispatch"
        assert candidate.get("channel") == "policy"
        assert candidate.get("salience") == 70
    finally:
        _cleanup(client, modules)
