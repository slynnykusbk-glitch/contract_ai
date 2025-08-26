import pytest

from contract_review_app.analysis.extract_summary import extract_document_snapshot

CASES = [
    (
        "Agency",
        """AGENCY AGREEMENT\nThe Principal appoints the Agent to solicit orders in the Territory for a commission.""",
    ),
    (
        "Franchise",
        """FRANCHISE AGREEMENT\nThe Franchisor grants the Franchisee rights to use the brand with royalty payments and brand standards.""",
    ),
    (
        "Guarantee",
        """DEED OF GUARANTEE\nThe Guarantor guarantees the obligations of the Principal Debtor and provides an indemnity.""",
    ),
]


@pytest.mark.parametrize("expected,text", CASES)
def test_document_type_classifier(expected: str, text: str):
    snap = extract_document_snapshot(text)
    assert snap.type == expected
    assert snap.type_confidence >= 0.6
