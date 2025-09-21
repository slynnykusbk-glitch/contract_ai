import os
import sys

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


_FIXTURE_TEXT = "Payment shall be made within 30 days."


def test_trace_artifacts_all_invariants():
    prev_companies = os.environ.get("FEATURE_COMPANIES_HOUSE")
    prev_llm_analyze = os.environ.get("FEATURE_LLM_ANALYZE")

    os.environ["FEATURE_COMPANIES_HOUSE"] = "0"
    os.environ["FEATURE_LLM_ANALYZE"] = "0"
    sys.modules.pop("contract_review_app.config", None)

    client, modules = _build_client("1")
    try:
        payload = {"text": _FIXTURE_TEXT}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200

        data = response.json()
        unexpected = {"features", "dispatch", "constraints", "proposals"}
        assert unexpected.isdisjoint(data)

        cid = response.headers.get("x-cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200
        trace_body = trace_response.json()

        for key in ("features", "dispatch", "constraints", "proposals"):
            assert key in trace_body

        features = trace_body.get("features") or {}
        doc = features.get("doc") or {}
        assert doc.get("length", 0) > 0

        segments = features.get("segments") or []
        assert segments
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            rng = segment.get("range") or {}
            start = rng.get("start")
            end = rng.get("end")
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert start < end

        dispatch = trace_body.get("dispatch") or {}
        ruleset = dispatch.get("ruleset") or {}
        loaded = ruleset.get("loaded")
        evaluated = ruleset.get("evaluated")
        triggered = ruleset.get("triggered")
        assert isinstance(loaded, int)
        assert isinstance(evaluated, int)
        assert isinstance(triggered, int)
        assert loaded >= evaluated >= triggered >= 0

        candidates = dispatch.get("candidates") or []
        candidate_rule_ids = {
            str(candidate.get("rule_id"))
            for candidate in candidates
            if isinstance(candidate, dict) and candidate.get("rule_id")
        }

        proposals = trace_body.get("proposals") or {}
        drafts = proposals.get("drafts") or []
        for draft in drafts:
            if not isinstance(draft, dict):
                continue
            rule_id = draft.get("rule_id")
            if not rule_id:
                continue
            assert str(rule_id) in candidate_rule_ids

        from contract_review_app.api import app as app_module

        trace_entry = app_module.TRACE.get(cid) or {}
        trace_meta = trace_entry.get("meta") or {}
        assert trace_meta.get("risk_threshold") in {"low", "medium", "high", "critical"}

        analysis = trace_body.get("analysis") or {}
        findings = analysis.get("findings") or []
        assert findings
        first_anchor = findings[0].get("anchor") if isinstance(findings[0], dict) else None
        assert isinstance(first_anchor, dict)
        assert first_anchor.get("method") in {"nth", "token", "text"}
    finally:
        _cleanup(client, modules)
        if prev_companies is None:
            os.environ.pop("FEATURE_COMPANIES_HOUSE", None)
        else:
            os.environ["FEATURE_COMPANIES_HOUSE"] = prev_companies
        if prev_llm_analyze is None:
            os.environ.pop("FEATURE_LLM_ANALYZE", None)
        else:
            os.environ["FEATURE_LLM_ANALYZE"] = prev_llm_analyze
        sys.modules.pop("contract_review_app.config", None)
