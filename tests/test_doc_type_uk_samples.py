import pytest
from contract_review_app.analysis.extract_summary import extract_document_snapshot

CASES = [
    (
        "DPA",
        "Background:\nData Processing Agreement for UK GDPR compliance.\nThe Processor shall assist the Controller.",
    ),
    (
        "Consultancy",
        "Scope:\nThis Consultancy Agreement outlines services for the Client by the Consultant.",
    ),
    (
        "Agency",
        "Purpose:\nAgency Agreement appointing an Agent to solicit orders in the UK for the Principal.",
    ),
]


@pytest.mark.parametrize("expected,text", CASES)
def test_doc_type_uk_samples(expected: str, text: str):
    snap = extract_document_snapshot(text)
    assert snap.type == expected
    assert snap.type_confidence >= 0.6
