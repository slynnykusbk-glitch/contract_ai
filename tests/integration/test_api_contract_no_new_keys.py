import os

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def test_api_contract_no_new_keys():
    previous_flag = os.environ.get("FEATURE_L0_LABELS")
    os.environ["FEATURE_L0_LABELS"] = "1"

    client, modules = _build_client("1")
    try:
        response = client.post(
            "/api/analyze", headers=_headers(), json={"text": "Hello"}
        )
        assert response.status_code == 200
        payload = response.json()
        expected_keys = {
            "analysis",
            "cid",
            "clauses",
            "document",
            "findings",
            "meta",
            "recommendations",
            "results",
            "rules_coverage",
            "schema_version",
            "status",
            "summary",
        }
        assert set(payload) == expected_keys
    finally:
        _cleanup(client, modules)
        if previous_flag is None:
            os.environ.pop("FEATURE_L0_LABELS", None)
        else:
            os.environ["FEATURE_L0_LABELS"] = previous_flag
