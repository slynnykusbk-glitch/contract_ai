from contract_review_app.analysis.parser import parse_text
from contract_review_app.analysis.lx_features import extract_l0_features


def _extract_labels(text: str):
    parsed = parse_text(text)
    features = extract_l0_features(parsed)
    segment = features.segments[1]
    return features, segment


def test_payment_duration_extraction():
    text = "Payment shall be made within sixty (60) days of receipt of invoice."
    features, segment = _extract_labels(text)

    assert "Payment" in segment.labels
    assert features.durations["days"] == 60
    assert segment.durations["days"] == 60


def test_term_duration_extraction():
    text = "This Agreement shall remain in force for forty-five (45) days from execution."
    features, segment = _extract_labels(text)

    assert "Term" in segment.labels
    assert features.durations["days"] == 45
    assert segment.durations["days"] == 45


def test_mixed_labels_are_detected():
    text = (
        "Payment shall be made within sixty (60) days of receipt of invoice.\n"
        "The term shall remain in force for forty-five (45) days from execution."
    )
    parsed = parse_text(text)
    features = extract_l0_features(parsed)

    first_segment = features.segments[1]
    second_segment = features.segments[2]

    assert "Payment" in first_segment.labels
    assert "Term" in second_segment.labels
    assert "Payment" in features.labels
    assert "Term" in features.labels
