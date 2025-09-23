import os
from typing import Any

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def _reasons_with_label(candidates, label: str) -> list[dict]:
    matches: list[dict] = []
    for candidate in candidates:
        reasons = candidate.get("reasons") or []
        for reason in reasons:
            labels = reason.get("labels") or []
            if label in labels:
                matches.append(reason)
    return matches


def _assert_reason_offsets(reasons: list[dict], bucket_key: str) -> None:
    assert reasons, f"expected reasons with bucket {bucket_key}"
    seen_offsets = False
    for reason in reasons:
        entries = reason.get(bucket_key) or []
        for entry in entries:
            offsets = entry.get("offsets") or []
            if offsets:
                seen_offsets = True
            assert isinstance(offsets, list)
            for span in offsets:
                assert isinstance(span, list)
                assert len(span) == 2
                assert all(isinstance(value, int) for value in span)
            lowered_keys = {str(key).lower() for key in entry.keys()}
            assert "text" not in lowered_keys
    assert seen_offsets, f"expected offsets in {bucket_key} entries"


def _assert_pattern_offsets(candidates: list[dict[str, Any]]) -> None:
    for candidate in candidates:
        reasons = candidate.get("reasons") or []
        for reason in reasons:
            patterns = reason.get("patterns") or []
            for pattern in patterns:
                offsets = pattern.get("offsets")
                assert isinstance(offsets, list)
                for span in offsets:
                    assert isinstance(span, list)
                    assert len(span) == 2
                    assert all(isinstance(value, int) for value in span)


def test_trace_dispatch_reason_offsets_in_buckets():
    previous_flag = os.environ.get("FEATURE_LX_ENGINE")
    previous_reason_flag = os.environ.get("FEATURE_REASON_OFFSETS")
    os.environ["FEATURE_LX_ENGINE"] = "1"
    os.environ["FEATURE_REASON_OFFSETS"] = "1"
    client, modules = _build_client("1")
    try:
        payload = {
            "text": (
                "Supplier shall be paid £10,000 within 30 days. "
                "This Agreement is governed by the laws of England "
                "and the courts of England shall have exclusive jurisdiction."
            )
        }
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200

        body = response.json()
        timings = ((body.get("meta") or {}).get("timings_ms") or {})
        assert "dispatch_ms" in timings
        assert isinstance(timings["dispatch_ms"], (int, float))

        cid = response.headers.get("x-cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200
        trace_body = trace_response.json()

        dispatch = trace_body.get("dispatch") or {}
        candidates = dispatch.get("candidates") or []
        assert candidates, "expected dispatch candidates"

        _assert_pattern_offsets(candidates)

        amount_reasons = _reasons_with_label(candidates, "amount")
        duration_reasons = _reasons_with_label(candidates, "duration")
        law_reasons = _reasons_with_label(candidates, "law")
        jurisdiction_reasons = _reasons_with_label(candidates, "jurisdiction")

        _assert_reason_offsets(amount_reasons, "amounts")
        _assert_reason_offsets(duration_reasons, "durations")
        _assert_reason_offsets(law_reasons, "law")
        _assert_reason_offsets(jurisdiction_reasons, "jurisdiction")
    finally:
        _cleanup(client, modules)
        if previous_flag is None:
            os.environ.pop("FEATURE_LX_ENGINE", None)
        else:
            os.environ["FEATURE_LX_ENGINE"] = previous_flag
        if previous_reason_flag is None:
            os.environ.pop("FEATURE_REASON_OFFSETS", None)
        else:
            os.environ["FEATURE_REASON_OFFSETS"] = previous_reason_flag

