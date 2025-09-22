from contract_review_app.analysis.parser import parse_text
from contract_review_app.analysis.lx_features import extract_l0_features
from contract_review_app.analysis.lx_features import extract_l0_features
from contract_review_app.analysis.parser import parse_text


def _extract_labels(text: str):
    parsed = parse_text(text)
    doc_features = extract_l0_features(parsed, parsed.segments)
    segment = doc_features.by_segment[1]
    return doc_features, segment


def test_payment_duration_extraction():
    text = "These payment terms require payment within sixty (60) days of invoice."
    doc_features, segment = _extract_labels(text)

    assert "payment_terms" in segment.labels

    durations = segment.entities.get("durations")
    assert isinstance(durations, list) and durations
    first = durations[0]
    assert first["value"]["duration"] == "P60D"
    assert segment.durations["days"] == 60
    assert doc_features.by_segment[1].durations["days"] == 60


def test_term_duration_extraction():
    text = "The term of this Agreement shall remain in force for forty-five (45) days from execution."
    doc_features, segment = _extract_labels(text)

    assert "term" in segment.labels
    durations = segment.entities.get("durations")
    assert isinstance(durations, list) and durations
    assert durations[0]["value"]["duration"] == "P45D"
    assert segment.durations["days"] == 45
    assert doc_features.by_segment[1].durations["days"] == 45


def test_mixed_labels_are_detected():
    text = (
        "These payment terms require payment within sixty (60) days of invoice.\n"
        "The term of this Agreement shall remain in force for forty-five (45) days from execution."
    )
    parsed = parse_text(text)
    doc_features = extract_l0_features(parsed, parsed.segments)

    first_segment = doc_features.by_segment[1]
    second_segment = doc_features.by_segment[2]

    assert "payment_terms" in first_segment.labels
    assert "term" in second_segment.labels

    all_labels = {
        label for fs in doc_features.by_segment.values() for label in fs.labels
    }
    assert "payment_terms" in all_labels
    assert "term" in all_labels
