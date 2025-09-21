from __future__ import annotations

import os

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def test_trace_constraints_payload_contains_checks() -> None:
    prev_lx_engine = os.environ.get("FEATURE_LX_ENGINE")
    prev_l2_constraints = os.environ.get("LX_L2_CONSTRAINTS")
    os.environ["FEATURE_LX_ENGINE"] = "1"
    os.environ["LX_L2_CONSTRAINTS"] = "1"

    client, modules = _build_client("1")
    try:
        payload = {"text": "Payment shall be made within thirty (30) days."}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200

        cid = response.headers.get("x-cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200

        body = trace_response.json()
        constraints = body.get("constraints")
        assert isinstance(constraints, dict)

        checks = constraints.get("checks")
        assert isinstance(checks, list)

        for entry in checks:
            assert isinstance(entry, dict)
            assert entry.get("result") in {"pass", "fail", "skip"}
    finally:
        _cleanup(client, modules)
        if prev_lx_engine is None:
            os.environ.pop("FEATURE_LX_ENGINE", None)
        else:
            os.environ["FEATURE_LX_ENGINE"] = prev_lx_engine
        if prev_l2_constraints is None:
            os.environ.pop("LX_L2_CONSTRAINTS", None)
        else:
            os.environ["LX_L2_CONSTRAINTS"] = prev_l2_constraints
