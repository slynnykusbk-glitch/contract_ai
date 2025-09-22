from typing import Any, Dict

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


ALLOWED_MATCH_KEYS = {"kind", "pattern_id", "offsets", "hash8", "len"}


def _assert_no_text_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            assert str(key).lower() != "text"
            _assert_no_text_keys(item)
    elif isinstance(value, (list, tuple, set)):
        for entry in value:
            _assert_no_text_keys(entry)


def test_dispatch_matches_have_no_raw_text():
    client, modules = _build_client("trace-privacy-no-text")
    try:
        payload = {"text": "Payment shall be made within 30 days of invoice."}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200

        cid = response.headers.get("x-cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200
        trace_body = trace_response.json()

        dispatch: Dict[str, Any] = trace_body.get("dispatch") or {}
        candidates = dispatch.get("candidates") or []

        _assert_no_text_keys(dispatch)

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            triggers = candidate.get("triggers") or {}
            matched = triggers.get("matched") or []
            for match in matched:
                assert isinstance(match, dict)
                lower_keys = {str(key).lower() for key in match.keys()}
                assert "text" not in lower_keys
                assert lower_keys <= ALLOWED_MATCH_KEYS
                if "offsets" in match:
                    offsets = match["offsets"]
                    assert isinstance(offsets, list)
                    for pair in offsets:
                        assert isinstance(pair, list)
                        assert len(pair) == 2
                        assert all(isinstance(val, int) for val in pair)
                if "hash8" in match:
                    assert isinstance(match["hash8"], str)
                    assert len(match["hash8"]) == 8
                if "len" in match:
                    assert isinstance(match["len"], int)
                    assert match["len"] >= 0
    finally:
        _cleanup(client, modules)
