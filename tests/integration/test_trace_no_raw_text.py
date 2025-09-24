from __future__ import annotations

from typing import Any, Tuple

import pytest

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)

FORBIDDEN_KEYS = {"text", "before", "after", "context", "raw"}


def _walk_forbidden(
    value: Any,
    path: Tuple[str, ...],
    errors: list[str],
    allow_snippet: bool,
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            current_path = path + (str(key),)
            if lower in FORBIDDEN_KEYS:
                errors.append("/".join(current_path))
                continue
            if lower == "snippet":
                if not allow_snippet:
                    errors.append("/".join(current_path))
                    continue
                if not isinstance(item, str):
                    errors.append("/".join(current_path))
                    continue
                if len(item) > 200:
                    errors.append("/".join(current_path))
                    continue
                continue
            _walk_forbidden(item, current_path, errors, allow_snippet)
    elif isinstance(value, (list, tuple, set)):
        for idx, item in enumerate(value):
            _walk_forbidden(item, path + (str(idx),), errors, allow_snippet)


def _assert_section_clean(section: Any, allow_snippet: bool = False) -> None:
    if section is None:
        return
    errors: list[str] = []
    _walk_forbidden(section, tuple(), errors, allow_snippet)
    if errors:
        pytest.fail("forbidden raw-text keys found: " + ", ".join(sorted(errors)))


def test_trace_no_raw_text_leaks():
    client, modules = _build_client("trace-no-raw")
    try:
        payload = {"text": "This agreement shall terminate if payment is not made."}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200

        cid = response.headers.get("x-cid")
        assert cid
        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200
        trace_body = trace_response.json()

        _assert_section_clean(trace_body.get("features"))
        _assert_section_clean(trace_body.get("dispatch"))
        _assert_section_clean(trace_body.get("constraints"))
        _assert_section_clean(trace_body.get("proposals"), allow_snippet=True)
    finally:
        _cleanup(client, modules)
