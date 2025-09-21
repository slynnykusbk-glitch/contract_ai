from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def test_features_block_present():
    client, modules = _build_client("1")
    try:
        payload = {"text": "Payment is due within 30 days.\nThe term lasts 12 months."}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200
        body = response.json()
        cid = response.headers.get("x-cid") or body.get("cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200
        trace_body = trace_response.json()

        features = trace_body.get("features")
        assert isinstance(features, dict)

        doc = features.get("doc")
        assert isinstance(doc, dict)
        assert isinstance(doc.get("language"), str) and doc.get("language")
        assert isinstance(doc.get("length"), int) and doc.get("length") > 0
        doc_hash = doc.get("hash")
        assert isinstance(doc_hash, str) and len(doc_hash) == 64

        segments = features.get("segments")
        assert isinstance(segments, list)
        assert segments

        first_segment = segments[0]
        assert isinstance(first_segment, dict)
        assert first_segment.get("id") is not None

        seg_range = first_segment.get("range")
        assert isinstance(seg_range, dict)
        assert isinstance(seg_range.get("start"), int)
        assert isinstance(seg_range.get("end"), int)
        assert seg_range["end"] >= seg_range["start"]

        labels = first_segment.get("labels")
        assert isinstance(labels, list)

        tokens = first_segment.get("tokens")
        assert isinstance(tokens, dict)
        assert isinstance(tokens.get("len"), int)
    finally:
        _cleanup(client, modules)


def test_proposals_block_present():
    client, modules = _build_client("1")
    try:
        payload = {
            "text": (
                "This payment clause applies to a contracting authority and must comply with Regulation 113.\n"
                "Payment notice and pay-less notice under the Construction Act applies."
            )
        }
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200
        body = response.json()
        cid = response.headers.get("x-cid") or body.get("cid")
        assert cid

        trace_response = client.get(f"/api/trace/{cid}")
        assert trace_response.status_code == 200
        trace_body = trace_response.json()

        proposals = trace_body.get("proposals")
        assert isinstance(proposals, dict)

        drafts = proposals.get("drafts")
        assert isinstance(drafts, list)
        assert drafts

        merged = proposals.get("merged")
        assert isinstance(merged, list)
        assert merged

        first_draft = drafts[0]
        assert isinstance(first_draft.get("rule_id"), str) and first_draft["rule_id"]
        assert isinstance(first_draft.get("ops"), list)
        assert first_draft["ops"]

        first_merged = merged[0]
        assert isinstance(first_merged.get("rule_id"), str) and first_merged["rule_id"]
        assert isinstance(first_merged.get("ops"), list)
        assert first_merged["ops"]

        assert first_draft["rule_id"] == first_merged["rule_id"]
    finally:
        _cleanup(client, modules)
