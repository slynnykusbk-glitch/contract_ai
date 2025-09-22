import os

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


def _sanitize_env(key: str, value: str) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


def test_trace_features_include_labels_and_entities():
    previous_l0 = os.environ.get("FEATURE_L0_LABELS")
    previous_trace = os.environ.get("FEATURE_TRACE_ARTIFACTS")
    _sanitize_env("FEATURE_L0_LABELS", "1")
    _sanitize_env("FEATURE_TRACE_ARTIFACTS", "1")

    client, modules = _build_client("1")
    try:
        payload = {
            "text": (
                "Invoices are payable within thirty (30) days.\n"
                "Payment Terms. The Supplier shall be paid within thirty (30) days of invoice.\n"
                "Term. This agreement continues for sixty (60) days from the Effective Date.\n"
                "Governing Law. The parties agree to English law and submit to the courts of London."
            )
        }
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
        assert isinstance(doc.get("language"), str)
        assert isinstance(doc.get("length"), int)
        assert isinstance(doc.get("hash"), str)

        segments = features.get("segments")
        assert isinstance(segments, list)
        assert segments

        payment_segments = []
        for segment in segments:
            assert isinstance(segment, dict)
            labels = segment.get("labels")
            assert isinstance(labels, list)
            assert labels
            if "payment_terms" in labels:
                payment_segments.append(segment)

            entities = segment.get("entities")
            assert isinstance(entities, dict)
            assert entities
            for key, values in entities.items():
                assert key in {
                    "amounts",
                    "percentages",
                    "durations",
                    "dates",
                    "incoterms",
                    "law",
                    "jurisdiction",
                }
                assert isinstance(values, list)
                for entry in values:
                    assert isinstance(entry, dict)
                    assert "text" not in entry
                    assert "start" in entry and "end" in entry
                    assert "value" in entry
                    value = entry.get("value")
                    if isinstance(value, dict):
                        assert "text" not in value

        assert payment_segments

        for segment in payment_segments:
            durations = segment.get("entities", {}).get("durations", [])
            if durations:
                assert any(
                    (
                        entry.get("unit") == "days" and entry.get("value") == 30
                    )
                    or (
                        isinstance(entry.get("value"), dict)
                        and entry["value"].get("days") == 30
                    )
                    for entry in durations
                    if isinstance(entry, dict)
                )
                break
    finally:
        _cleanup(client, modules)
        if previous_l0 is None:
            os.environ.pop("FEATURE_L0_LABELS", None)
        else:
            os.environ["FEATURE_L0_LABELS"] = previous_l0
        if previous_trace is None:
            os.environ.pop("FEATURE_TRACE_ARTIFACTS", None)
        else:
            os.environ["FEATURE_TRACE_ARTIFACTS"] = previous_trace
