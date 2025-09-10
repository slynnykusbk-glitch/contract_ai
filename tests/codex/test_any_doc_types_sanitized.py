from pathlib import Path

from contract_review_app.legal_rules.loader import load_rule_packs, filter_rules

TEXT = Path("fixtures/contracts/mixed_sample.txt").read_text(encoding="utf-8")
DOC_TYPES = ["NDA", "MSA (Services)", "Consultancy"]


def test_sanitized_doc_types_no_duplicates():
    load_rule_packs()
    for dt in DOC_TYPES:
        matched, _ = filter_rules(TEXT, doc_type=dt, clause_types=[], jurisdiction="UK")
        ids = [m["rule"]["id"] for m in matched]
        assert len(ids) == len(set(ids))
        assert 8 <= len(ids) <= 20
