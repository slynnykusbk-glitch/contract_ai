import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from contract_review_app.suggest import build_edits


def test_governing_law_edit_replaces_span():
    text = "This Agreement is governed by the laws of Scotland."
    span_text = "governed by the laws of Scotland"
    start = text.index(span_text)
    end = start + len(span_text)
    findings = [{"clause_type": "governing_law", "span": {"start": start, "end": end}}]

    edits = build_edits(text, "governing_law", findings, mode="friendly")

    assert isinstance(edits, list) and len(edits) >= 1
    rng = edits[0]["range"]
    assert rng["length"] > 0
    assert "England and Wales" in edits[0]["replacement"]
