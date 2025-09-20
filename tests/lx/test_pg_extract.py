from decimal import Decimal
from types import SimpleNamespace

from contract_review_app.analysis.extract_summary import extract_document_snapshot
from contract_review_app.analysis.lx_features import extract_l0_features
from contract_review_app.analysis.parser import parse_text
from contract_review_app.core.lx_types import Duration, ParamGraph
from contract_review_app.legal_rules.constraints import build_param_graph


CONTRACT_TEXT = """
This Services Agreement (the "Agreement") is made between Acme Corp (the "Seller") and Beta LLC (the "Buyer").

1. PAYMENT TERMS
Payment shall be made net 30 days from the date of invoice. Late payments incur interest after a grace period of five (5) days.

2. TERM AND TERMINATION
2.1 Term. The Agreement shall remain in force for sixty (60) days from the Effective Date.
2.2 Termination for Convenience. Either party may terminate this Agreement for convenience upon thirty (30) days' prior written notice.
2.3 Cure. The breaching party shall cure any breach within fifteen (15) business days after notice.
The following provisions shall survive termination: confidentiality and limitation of liability.

4. MISCELLANEOUS
See Clause 2.1 for details about the Term. Annex A describes the deliverables. The parties acknowledge the "Service Credits" shall apply when service levels are missed.

GOVERNING LAW
This Agreement shall be governed by the laws of England and Wales, and the parties submit to the exclusive jurisdiction of the courts of Scotland.

LIABILITY
The aggregate liability of either party shall be capped at £500,000.

SIGNED by John Doe on 1 January 2024
"""


REORDERED_TEXT = """
This Services Agreement (the "Agreement") is made between Acme Corp (the "Seller") and Beta LLC (the "Buyer").

4. MISCELLANEOUS
See Clause 2.1 for details about the Term. Annex A describes the deliverables. The parties acknowledge the "Service Credits" shall apply when service levels are missed.

2. TERM AND TERMINATION
2.1 Term. The Agreement shall remain in force for sixty (60) days from the Effective Date.
2.2 Termination for Convenience. Either party may terminate this Agreement for convenience upon thirty (30) days' prior written notice.
2.3 Cure. The breaching party shall cure any breach within fifteen (15) business days after notice.
The following provisions shall survive termination: confidentiality and limitation of liability.

1. PAYMENT TERMS
Payment shall be made net 30 days from the date of invoice. Late payments incur interest after a grace period of five (5) days.

GOVERNING LAW
This Agreement shall be governed by the laws of England and Wales, and the parties submit to the exclusive jurisdiction of the courts of Scotland.

LIABILITY
The aggregate liability of either party shall be capped at £500,000.

SIGNED by John Doe on 1 January 2024
"""


def _build_pg(text: str) -> ParamGraph:
    parsed = parse_text(text)
    snapshot = extract_document_snapshot(text)
    features = extract_l0_features(text, parsed.segments)
    return build_param_graph(snapshot, parsed.segments, features)


def test_param_graph_extracts_core_parameters():
    pg = _build_pg(CONTRACT_TEXT)

    assert isinstance(pg.payment_term, Duration)
    assert pg.payment_term.days == 30
    assert pg.payment_term.kind == "calendar"

    assert isinstance(pg.notice_period, Duration)
    assert pg.notice_period.days == 30

    assert isinstance(pg.cure_period, Duration)
    assert pg.cure_period.days == 21
    assert pg.cure_period.kind == "business"

    assert isinstance(pg.grace_period, Duration)
    assert pg.grace_period.days == 5

    assert isinstance(pg.contract_term, Duration)
    assert pg.contract_term.days == 60

    assert pg.governing_law == "England and Wales"
    assert "Scotland" in (pg.jurisdiction or "")

    assert pg.cap is not None
    assert pg.cap.amount == Decimal("500000")
    assert pg.cap.currency == "GBP"

    assert pg.contract_currency == "GBP"

    assert sorted(pg.survival_items) == ["confidentiality", "limitation of liability"]

    assert ("4", "2.1") in pg.cross_refs
    assert pg.annex_refs == ["Annex A"]
    assert pg.order_of_precedence is False

    assert "Service Credits" in pg.undefined_terms
    assert pg.numbering_gaps == [3]

    assert len(pg.parties) == 2
    party_names = sorted(p.get("name") for p in pg.parties)
    assert party_names == ["Acme Corp", "Beta LLC"]

    assert pg.signatures and "John Doe" in pg.signatures[0]["raw"]

    assert {"payment_term", "notice_period", "cure_period", "cap"}.issubset(pg.sources.keys())
    assert pg.sources["payment_term"].clause_id == "1"


def test_param_graph_stable_under_reordering():
    pg_original = _build_pg(CONTRACT_TEXT)
    pg_reordered = _build_pg(REORDERED_TEXT)

    assert pg_original.payment_term == pg_reordered.payment_term
    assert pg_original.notice_period == pg_reordered.notice_period
    assert pg_original.cure_period == pg_reordered.cure_period
    assert pg_original.governing_law == pg_reordered.governing_law
    assert pg_original.jurisdiction == pg_reordered.jurisdiction
    assert pg_original.cap == pg_reordered.cap
    assert pg_original.contract_currency == pg_reordered.contract_currency
    assert pg_original.survival_items == pg_reordered.survival_items
    assert pg_original.cross_refs == pg_reordered.cross_refs
    assert pg_original.annex_refs == pg_reordered.annex_refs
    assert pg_original.undefined_terms == pg_reordered.undefined_terms
    assert pg_original.numbering_gaps == pg_reordered.numbering_gaps


def test_param_graph_threads_doc_flags_from_snapshot():
    snapshot = SimpleNamespace(
        parties=[],
        signatures=[],
        liability=None,
        governing_law=None,
        jurisdiction=None,
        currency=None,
        doc_flags={"flag_a": True, "flag_b": False},
    )

    pg = build_param_graph(snapshot, [], None)

    assert pg.doc_flags == {"flag_a": True, "flag_b": False}


def test_param_graph_threads_doc_flags_from_debug():
    snapshot = SimpleNamespace(
        parties=[],
        signatures=[],
        liability=None,
        governing_law=None,
        jurisdiction=None,
        currency=None,
        debug={"doc_flags": {"flag_c": True}},
    )

    pg = build_param_graph(snapshot, [], None)

    assert pg.doc_flags == {"flag_c": True}
