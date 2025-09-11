from pathlib import Path
from contract_review_app.engine.pipeline import analyze_document


def test_blackrock_routing():
    text = Path("tests/e2e/fixtures/blackrock_nda.txt").read_text(encoding="utf-8")
    doc = analyze_document(text)
    summary = getattr(doc, "summary", {})
    assert summary.get("type") == "NDA"
    assert summary.get("jurisdiction") == "UK"
    packs = summary.get("active_packs") or []
    assert "uk_nda_pack" in packs
    assert summary.get("rules_evaluated", 0) > 0
