from contract_review_app.analysis.parser import parse_text
from contract_review_app.analysis.lx_features import extract_l0_features


def _extract_labels(text: str):
    parsed = parse_text(text)
    doc_features = extract_l0_features(text, parsed.segments)
    segment = doc_features.by_segment[1]
    return doc_features, segment


def test_payment_duration_extraction():
    text = "Payment shall be made within sixty (60) days of receipt of invoice."
    doc_features, segment = _extract_labels(text)

    assert "Payment" in segment.labels
    assert segment.durations["days"] == 60
    assert doc_features.by_segment[1].durations["days"] == 60


def test_term_duration_extraction():
    text = "This Agreement shall remain in force for forty-five (45) days from execution."
    doc_features, segment = _extract_labels(text)

    assert "Term" in segment.labels
    assert segment.durations["days"] == 45
    assert doc_features.by_segment[1].durations["days"] == 45


def test_mixed_labels_are_detected():
    text = (
        "Payment shall be made within sixty (60) days of receipt of invoice.\n"
        "The term shall remain in force for forty-five (45) days from execution."
    )
    parsed = parse_text(text)
    doc_features = extract_l0_features(text, parsed.segments)

    first_segment = doc_features.by_segment[1]
    second_segment = doc_features.by_segment[2]

    assert "Payment" in first_segment.labels
    assert "Term" in second_segment.labels

    all_labels = {
        label for fs in doc_features.by_segment.values() for label in fs.labels
    }
    assert "Payment" in all_labels
    assert "Term" in all_labels
