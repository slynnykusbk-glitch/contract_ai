import copy
from typing import Any

from contract_review_app.api.models import SCHEMA_VERSION


def _reset_trace(trace_store: Any) -> None:
    trace_store._data.clear()
    trace_store._weights.clear()
    trace_store._total_weight = 0


def _clear_analyze_cache(app_module: Any) -> None:
    for cache in (app_module.an_cache, app_module.cid_index, app_module.gpt_cache):
        cache._data.clear()
    if hasattr(app_module, "IDEMPOTENCY_CACHE"):
        app_module.IDEMPOTENCY_CACHE.clear()


def _collect_reasons(trace_entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(trace_entry, dict):
        return []
    body = trace_entry.get("body")
    if not isinstance(body, dict):
        return []
    dispatch = body.get("dispatch")
    if not isinstance(dispatch, dict):
        return []
    reasons: list[dict[str, Any]] = []
    candidates = dispatch.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            bucket = candidate.get("reasons")
            if isinstance(bucket, list):
                for reason in bucket:
                    if isinstance(reason, dict):
                        reasons.append(reason)
    return reasons


def _has_offsets(reason: dict[str, Any]) -> bool:
    for key in ("patterns", "amounts", "durations", "law", "jurisdiction"):
        bucket = reason.get(key)
        if not isinstance(bucket, list):
            continue
        for entry in bucket:
            if isinstance(entry, dict) and "offsets" in entry:
                return True
    return False


def _normalize_response(data: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(data)
    normalized.pop("cid", None)
    meta = normalized.get("meta")
    if isinstance(meta, dict):
        meta = dict(meta)
        for key in ("pipeline_id", "timings_ms", "debug"):
            meta.pop(key, None)
        normalized["meta"] = meta
    return normalized


def test_reason_offsets_feature_flag(api, monkeypatch):
    from contract_review_app.api import app as app_module

    monkeypatch.setenv("DEV_MODE", "1")
    monkeypatch.setenv("ALLOW_DEV_KEY_INJECTION", "1")
    monkeypatch.setenv("DEFAULT_API_KEY", "local-test-key-123")
    monkeypatch.setenv("FEATURE_LX_ENGINE", "1")
    monkeypatch.setenv("FEATURE_TRACE_ARTIFACTS", "1")
    monkeypatch.setattr(app_module, "FEATURE_LX_ENGINE", True, raising=False)
    monkeypatch.setattr(app_module, "FEATURE_TRACE_ARTIFACTS", True, raising=False)

    payload = {"text": "Payment shall be made within 30 days."}

    def _run(flag_enabled: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        monkeypatch.setenv("FEATURE_REASON_OFFSETS", "1" if flag_enabled else "0")
        monkeypatch.setattr(
            app_module, "FEATURE_REASON_OFFSETS", flag_enabled, raising=False
        )
        _reset_trace(app_module.TRACE)
        _clear_analyze_cache(app_module)

        response = api.post(
            "/api/analyze",
            json=payload,
            headers={
                "x-api-key": "local-test-key-123",
                "x-schema-version": SCHEMA_VERSION,
                "x-cid": "test-cid-reason-offsets",
            },
        )
        assert response.status_code == 200

        data = response.json()
        cid = response.headers.get("x-cid")
        assert cid

        trace_entry = app_module.TRACE.get(cid) or {}
        reasons = _collect_reasons(trace_entry)
        assert reasons, "expected at least one reason entry in TRACE"
        return data, reasons

    data_on, reasons_on = _run(True)
    data_off, reasons_off = _run(False)

    assert _normalize_response(data_on) == _normalize_response(data_off)

    assert any(_has_offsets(reason) for reason in reasons_on)
    for reason in reasons_off:
        assert not _has_offsets(reason)
