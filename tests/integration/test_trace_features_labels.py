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
    previous_flag = os.environ.get("FEATURE_L0_LABELS")
    _sanitize_env("FEATURE_L0_LABELS", "1")

    client, modules = _build_client("1")
    try:
        payload = {
            "text": (
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

        for segment in segments:
            assert isinstance(segment, dict)
            labels = segment.get("labels")
            assert isinstance(labels, list)
            assert labels

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

    finally:
        _cleanup(client, modules)
        if previous_flag is None:
            os.environ.pop("FEATURE_L0_LABELS", None)
        else:
            os.environ["FEATURE_L0_LABELS"] = previous_flag
