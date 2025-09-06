from pathlib import Path
import pytest
from contract_review_app.intake.parser import ParsedDocument

FIXTURES = [
    "tests/fixtures/intake_simple.txt",
    "tests/fixtures/intake_mixed.txt",
    "tests/fixtures/intake_fancy.txt",
]


@pytest.mark.parametrize("fname", FIXTURES)
def test_span_invariants(fname: str) -> None:
    raw = Path(fname).read_text(encoding="utf-8")
    doc = ParsedDocument.from_text(raw)

    assert all(
        0 <= doc.offset_map[i] < len(doc.content)
        and doc.offset_map[i] < doc.offset_map[i + 1]
        for i in range(len(doc.offset_map) - 1)
    )

    spans = [(int(s["start"]), int(s["end"])) for s in doc.segments]
    spans.sort()
    prev_end = 0
    for start, end in spans:
        assert prev_end <= start
        assert start < end
        prev_end = end

    nt = doc.normalized_text
    total = sum(1 for ch in nt if not ch.isspace())
    covered = 0
    for start, end in spans:
        covered += sum(1 for ch in nt[start:end] if not ch.isspace())
    if total:
        assert covered / total >= 0.995
