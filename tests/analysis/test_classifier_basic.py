from contract_review_app.analysis.classifier import classify_segments


def test_classifier_basic():
    segments = [
        {"heading": "GOVERNING LAW", "text": "This agreement is governed by the laws of England and Wales."},
        {"heading": "", "text": "Each party shall keep the confidential information secret."},
        {"heading": "Data Protection", "text": "Supplier complies with Data Protection Act 1998."},
    ]
    classify_segments(segments)
    assert segments[0]["clause_type"] == "governing_law"
    assert segments[1]["clause_type"] == "confidentiality"
    assert segments[2]["clause_type"] == "data_protection"
