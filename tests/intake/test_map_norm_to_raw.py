from pathlib import Path
import random
from contract_review_app.intake.parser import ParsedDocument
from contract_review_app.intake.normalization import normalize_text


def test_map_norm_span_to_raw_roundtrip() -> None:
    raw = Path("tests/fixtures/intake_fancy.txt").read_text(encoding="utf-8")
    doc = ParsedDocument.from_text(raw)
    nt = doc.normalized_text
    rnd = random.Random(12345)
    if len(nt) <= 1:
        return
    for _ in range(50):
        a = rnd.randrange(0, len(nt) - 1)
        b = rnd.randrange(a + 1, len(nt) + 1)
        span = doc.map_norm_span_to_raw(a, b)
        assert span is not None
        s, e = span
        assert 0 <= s < e <= len(doc.content)
        piece = doc.content[s:e]
        assert piece
        norm_piece, _ = normalize_text(piece)
        assert norm_piece == nt[a:b]
