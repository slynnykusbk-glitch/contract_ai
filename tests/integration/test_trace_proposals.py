from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def test_trace_proposals_snapshots_present_and_linked_to_dispatch():
    client, modules = _build_client("1")
    try:
        payload = {"text": "Payment shall be made within 30 days."}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200

        cid = response.headers.get("x-cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200

        trace_body = trace_response.json()
        proposals = trace_body.get("proposals")
        assert isinstance(proposals, dict)

        drafts = proposals.get("drafts")
        merged = proposals.get("merged")
        assert isinstance(drafts, list)
        assert isinstance(merged, list)

        dispatch = trace_body.get("dispatch") or {}
        assert isinstance(dispatch, dict)
        candidates = dispatch.get("candidates") or []
        candidate_rule_ids = {
            str(candidate.get("rule_id"))
            for candidate in candidates
            if isinstance(candidate, dict) and candidate.get("rule_id")
        }

        for draft in drafts:
            assert isinstance(draft, dict)
            rule_id = draft.get("rule_id")
            if not rule_id:
                continue
            assert str(rule_id) in candidate_rule_ids
    finally:
        _cleanup(client, modules)
