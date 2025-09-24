from pathlib import Path

from contract_review_app.core.lx_types import LxFeatureSet, LxSegment
from contract_review_app.legal_rules import dispatcher

FIXTURE_DIR = Path("fixtures/lx")


def _segment_and_features(
    name: str, labels: list[str]
) -> tuple[LxSegment, LxFeatureSet]:
    text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    segment = LxSegment(segment_id=99, heading="Test", text=text)
    features = LxFeatureSet(labels=labels)
    return segment, features


def _rule_ids(name: str, labels: list[str]) -> set[str]:
    segment, features = _segment_and_features(name, labels)
    refs = dispatcher.select_candidate_rules(segment, features)
    return {ref.rule_id for ref in refs}


def test_label_monotonicity_with_interest():
    base_ids = _rule_ids("seg_payment_60d.txt", ["Payment"])
    enriched_ids = _rule_ids("seg_payment_60d.txt", ["Payment", "Interest"])
    assert base_ids <= enriched_ids


def test_dispatch_is_deterministic():
    segment, features = _segment_and_features("seg_liability_cap.txt", ["Liability"])
    first = dispatcher.select_candidate_rules(segment, features)
    second = dispatcher.select_candidate_rules(segment, features)
    assert first == second
