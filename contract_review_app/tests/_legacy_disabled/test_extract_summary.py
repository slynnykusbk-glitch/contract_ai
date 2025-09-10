import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from contract_review_app.analysis.extract_summary import extract_document_snapshot


def test_extract_law_and_term_and_liability():
    text = (
        "This Agreement shall commence on 1 January 2024 and continue for a period of 2 years "
        "unless either party gives 30 days notice. This Agreement is governed by the laws of England and Wales "
        "and parties submit to the exclusive jurisdiction of the courts of England. The liability of either party "
        "shall not exceed £100,000. The Seller warrants that goods conform. The following is a condition of this Agreement."
    )
    snap = extract_document_snapshot(text)
    assert snap.term.start == "1 January 2024"
    assert snap.term.mode == "auto_renew"
    assert snap.term.renew_notice == "30"
    assert snap.governing_law == "England and Wales"
    assert snap.jurisdiction == "England"
    assert snap.exclusivity is True
    assert snap.liability.has_cap is True
    assert abs(snap.liability.cap_value - 100000) < 1e-6
    assert snap.liability.cap_currency == "GBP"
    assert snap.conditions_vs_warranties.has_conditions is True
    assert snap.conditions_vs_warranties.has_warranties is True
