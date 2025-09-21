from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def test_trace_features_snapshot():
    client, modules = _build_client("1")
    try:
        payload = {"text": "Section 1. Duties\nSection 2. Termination"}
        response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert response.status_code == 200
        cid = response.headers.get("x-cid")
        assert cid

        trace = client.get(f"/api/trace/{cid}")
        assert trace.status_code == 200
        body = trace.json()
        features = body.get("features")
        assert isinstance(features, dict)

        doc = features.get("doc")
        assert isinstance(doc, dict)
        assert doc.get("length", 0) > 0
        assert isinstance(doc.get("hints"), list)
        assert doc.get("language")

        segments = features.get("segments")
        assert isinstance(segments, list)
        assert segments  # should have entries even without rules
        for seg in segments:
            assert isinstance(seg, dict)
            seg_range = seg.get("range")
            assert isinstance(seg_range, dict)
            start = seg_range.get("start")
            end = seg_range.get("end")
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert start < end
            tokens = seg.get("tokens", {})
            assert isinstance(tokens, dict)
            assert tokens.get("len") >= 0
    finally:
        _cleanup(client, modules)
