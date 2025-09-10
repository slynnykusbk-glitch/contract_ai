from contract_review_app.intake.parser import ParsedDocument


def test_empty_text() -> None:
    doc = ParsedDocument.from_text("")
    assert doc.content == ""
    assert doc.normalized_text == ""
    assert doc.offset_map == []
    assert doc.segments == []


def test_basic_latin() -> None:
    raw = "Hello world."
    doc = ParsedDocument.from_text(raw)
    assert doc.normalized_text == raw
    assert doc.offset_map == list(range(len(raw)))
    assert doc.map_norm_to_raw(3) == 3
    assert doc.map_norm_span_to_raw(0, 5) == (0, 5)
    assert len(doc.segments) == 1
    seg = doc.segments[0]
    assert seg["start"] == 0 and seg["end"] == len(raw)
    assert seg["lang"] == "en" and seg["script"] == "Latin"


def test_normalization_and_offset_map() -> None:
    raw = "“Hello\u00a0World”—A\u200dB"
    expected = '"Hello World"-AB'
    doc = ParsedDocument.from_text(raw)
    assert doc.normalized_text == expected
    assert len(doc.offset_map) == len(expected)
    assert all(
        doc.offset_map[i] <= doc.offset_map[i + 1]
        for i in range(len(doc.offset_map) - 1)
    )
    span = doc.map_norm_span_to_raw(0, len(expected))
    assert span == (0, len(raw))


def test_mixed_scripts() -> None:
    raw = "Hello Привіт!"
    doc = ParsedDocument.from_text(raw)
    assert doc.normalized_text == raw
    assert doc.offset_map == list(range(len(raw)))
    expected = [
        {"start": 0, "end": 5, "lang": "en", "script": "Latin"},
        {"start": 5, "end": 6, "lang": "und", "script": "Common"},
        {"start": 6, "end": 12, "lang": "uk", "script": "Cyrillic"},
        {"start": 12, "end": 13, "lang": "und", "script": "Common"},
    ]
    assert doc.segments == expected
    assert doc.offset_map == sorted(doc.offset_map)


def test_emoji_mapping() -> None:
    raw = "OK 👍"
    doc = ParsedDocument.from_text(raw)
    assert doc.normalized_text == raw
    idx = doc.normalized_text.index("👍")
    assert doc.map_norm_to_raw(idx) == raw.index("👍")
    assert doc.map_norm_span_to_raw(idx, idx + 1) == (idx, idx + 1)


def test_idempotence() -> None:
    raw = "“Hello World”—A‍B"
    doc1 = ParsedDocument.from_text(raw)
    doc2 = ParsedDocument.from_text(doc1.normalized_text)
    assert doc2.normalized_text == doc1.normalized_text
    assert doc2.offset_map == list(range(len(doc2.normalized_text)))
    assert doc2.segments == doc1.segments
