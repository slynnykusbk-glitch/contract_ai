from __future__ import annotations

import pytest

from contract_review_app.analysis import resolve_labels


@pytest.mark.parametrize(
    "text",
    [
        "Payment shall be made within 30 days of invoice date.",
        "Invoices are payable within thirty (30) days.",
        "Net thirty (30) days from receipt.",
        "Supplier shall be paid no later than fifteen (15) Business Days after acceptance.",
        "Payment is due within 10 working days.",
    ],
)
def test_payment_terms_positive(text: str) -> None:
    assert "payment_terms" in resolve_labels(text, None)


@pytest.mark.parametrize(
    "text",
    [
        "Payment schedule is monthly.",
    ],
)
def test_payment_terms_negative(text: str) -> None:
    assert "payment_terms" not in resolve_labels(text, None)
