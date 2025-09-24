import os
from http import HTTPStatus
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

import contract_review_app.api.app as app_module
from contract_review_app.api.models import SCHEMA_VERSION


@pytest.fixture(autouse=True)
def _feature_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEATURE_TRACE_ARTIFACTS", "1")
    monkeypatch.setenv("FEATURE_COVERAGE_MAP", "1")
    monkeypatch.setenv("FEATURE_REASON_OFFSETS", "1")
    monkeypatch.setenv("FEATURE_AGENDA_SORT", "1")
    monkeypatch.setenv("FEATURE_AGENDA_STRICT_MERGE", "0")
    monkeypatch.setattr(app_module, "FEATURE_TRACE_ARTIFACTS", True, raising=False)
    monkeypatch.setattr(app_module, "FEATURE_COVERAGE_MAP", True, raising=False)
    monkeypatch.setattr(app_module, "FEATURE_REASON_OFFSETS", True, raising=False)
    monkeypatch.setattr(app_module, "FEATURE_AGENDA_SORT", True, raising=False)
    monkeypatch.setattr(app_module, "FEATURE_AGENDA_STRICT_MERGE", False, raising=False)


def _minimal_request_body() -> Mapping[str, Any]:
    return {
        "text": (
            "Payment terms: invoices due within 30 days. "
            "Governing Law: England and Wales. "
            "Confidentiality shall survive termination for 3 years. "
        )
    }


def _headers() -> Mapping[str, str]:
    return {"x-api-key": "dummy", "x-schema-version": SCHEMA_VERSION}


def _no_raw_text(obj: Any, path: str = "") -> None:
    if isinstance(obj, str):
        assert len(obj) < 2000, f"raw text too large at {path}"
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            _no_raw_text(value, f"{path}[{idx}]")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            _no_raw_text(value, f"{path}.{key}" if path else key)


def test_full_bridge_smoke() -> None:
    client = TestClient(app_module.app)

    analyze_response = client.post(
        "/api/analyze", headers=_headers(), json=_minimal_request_body()
    )
    assert analyze_response.status_code == HTTPStatus.OK
    analyze_payload = analyze_response.json()
    cid = analyze_payload.get("cid") or analyze_response.headers.get("x-cid")
    assert isinstance(cid, str) and len(cid) >= 8

    trace_response = client.get(f"/api/trace/{cid}")
    assert trace_response.status_code == HTTPStatus.OK
    trace = trace_response.json()

    for key in ("features", "dispatch", "coverage", "constraints", "proposals"):
        assert key in trace, f"missing {key} in TRACE"

    coverage = trace["coverage"]
    assert coverage.get("version") == 1
    assert int(coverage.get("zones_total", 0)) >= 30

    dispatch = trace["dispatch"]
    rules_loaded = dispatch.get("rules_loaded")
    evaluated = dispatch.get("evaluated")
    if rules_loaded is None or evaluated is None:
        ruleset = dispatch.get("ruleset") or {}
        rules_loaded = rules_loaded if rules_loaded is not None else ruleset.get("loaded")
        evaluated = evaluated if evaluated is not None else ruleset.get("evaluated")
    assert int(rules_loaded or 0) >= 0
    assert int(evaluated or 0) >= 0

    timings = (trace.get("meta") or {}).get("timings_ms") or {}
    merge_ms = timings.get("merge_ms", 0)
    assert isinstance(merge_ms, (int, float))
    assert merge_ms >= 0

    reasons_cap = int(os.getenv("TRACE_REASON_MAX_OFFSETS_PER_TYPE", "4"))
    segments = dispatch.get("segments") or []
    if not segments:
        segments = dispatch.get("candidates") or []
    for segment in segments:
        candidates = segment.get("candidates") if isinstance(segment, dict) else None
        if candidates is None:
            candidates = [segment] if isinstance(segment, dict) else []
        for candidate in candidates:
            reasons = candidate.get("reasons", []) if isinstance(candidate, dict) else []
            for reason in reasons:
                offsets = reason.get("offsets", {}) if isinstance(reason, dict) else {}
                if isinstance(offsets, dict):
                    for _, arr in offsets.items():
                        if isinstance(arr, list):
                            assert len(arr) <= reasons_cap

    _no_raw_text(trace)

    client.close()
