from pathlib import Path

from contract_review_app.core.lx_types import LxFeatureSet, LxSegment
from contract_review_app.legal_rules import dispatcher

FIXTURE_DIR = Path("fixtures/lx")


def _read(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_payment_dispatch_includes_payment_rules():
    text = _read("seg_payment_60d.txt")
    segment = LxSegment(segment_id=1, heading="Payment Terms", text=text)
    features = LxFeatureSet(
        labels=["Payment", "Interest"],
        durations={"days": 60},
        law_signals=["Late Payment of Commercial Debts"],
        jurisdiction="England",
    )

    refs = dispatcher.select_candidate_rules(segment, features)
    ids = {ref.rule_id for ref in refs}

    assert "P4.PAYMENT_TERMS_AND_INTEREST" in ids
    assert "P3.LATE_INVOICE_TIMEBAR" in ids


def test_term_dispatch_includes_notice_rules():
    text = _read("seg_term_45d.txt")
    segment = LxSegment(segment_id=2, heading="Term", text=text, clause_type="term")
    features = LxFeatureSet(labels=["Term"], durations={"days": 45})

    refs = dispatcher.select_candidate_rules(segment, features)
    ids = {ref.rule_id for ref in refs}

    assert "13.ITP.NOTICE" in ids


def test_liability_dispatch_covers_caps():
    text = _read("seg_liability_cap.txt")
    segment = LxSegment(
        segment_id=3,
        heading="Limitation of Liability",
        text=text,
        clause_type="liability",
    )
    features = LxFeatureSet(
        labels=["Liability"], amounts=["100000"], liability_caps=["fees"]
    )

    refs = dispatcher.select_candidate_rules(segment, features)
    ids = {ref.rule_id for ref in refs}

    assert "ic.vicarious.liability.supervision_language" in ids
    assert ids  # ensure we never return an empty set for liability segments
