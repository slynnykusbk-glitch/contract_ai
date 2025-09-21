from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def test_trace_dispatch_rules_match_findings():
    client, modules = _build_client("1")
    try:
        payload = {"text": "Payment shall be made within 30 days."}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200
        analysis = response.json().get("analysis", {})
        findings = analysis.get("findings") or []
        finding_ids = {
            str(item.get("rule_id"))
            for item in findings
            if isinstance(item, dict) and item.get("rule_id")
        }

        cid = response.headers.get("x-cid")
        assert cid
        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200
        trace_body = trace_response.json()

        dispatch = trace_body.get("dispatch")
        assert isinstance(dispatch, dict)

        ruleset = dispatch.get("ruleset")
        assert isinstance(ruleset, dict)
        loaded = ruleset.get("loaded")
        evaluated = ruleset.get("evaluated")
        triggered = ruleset.get("triggered")
        assert isinstance(loaded, int)
        assert isinstance(evaluated, int)
        assert isinstance(triggered, int)
        assert loaded >= evaluated >= triggered >= 0

        candidates = dispatch.get("candidates")
        assert isinstance(candidates, list)

        constraints = trace_body.get("constraints") or {}
        constraint_checks = constraints.get("checks") or []
        failed_constraint_rules = {
            str(check.get("details", {}).get("rule_id"))
            for check in constraint_checks
            if isinstance(check, dict)
            and check.get("result") == "fail"
            and isinstance(check.get("details"), dict)
            and check["details"].get("rule_id")
        }

        gated_matches = [
            c
            for c in candidates
            if isinstance(c, dict)
            and c.get("gates_passed")
            and (c.get("triggers") or {}).get("matched")
        ]
        assert gated_matches, "expected at least one triggered candidate"

        for candidate in gated_matches:
            rule_id = str(candidate.get("rule_id"))
            assert rule_id in finding_ids or rule_id in failed_constraint_rules
            triggers = candidate.get("triggers") or {}
            matched = triggers.get("matched") or []
            for match in matched:
                assert isinstance(match, dict)
                lowered = {str(k).lower() for k in match.keys()}
                assert "text" not in lowered
                span = match.get("span") if isinstance(match.get("span"), dict) else {}
                has_span = bool(span)
                has_hash = "hash8" in match and "len" in match
                assert has_span or has_hash, "expected span or hash/len metadata"
    finally:
        _cleanup(client, modules)
