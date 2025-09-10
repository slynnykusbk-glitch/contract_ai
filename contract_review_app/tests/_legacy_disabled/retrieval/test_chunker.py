from contract_review_app.retrieval.chunker import chunk_text


def test_overlap_and_offsets_are_consistent():
    text = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 40)
    chunks = chunk_text(text, max_chars=200, overlap=40)
    assert len(chunks) > 1
    for i, ch in enumerate(chunks[:-1]):
        nxt = chunks[i + 1]
        overlap = ch.end - nxt.start
        assert overlap >= 35  # allow small tolerance
        assert text[ch.start:ch.end] == ch.text
        assert ch.start < ch.end <= len(text)


def test_checksum_and_determinism():
    text = "Sentence one. Sentence two. Sentence three." * 5
    c1 = chunk_text(text)
    c2 = chunk_text(text)
    sig1 = [(c.start, c.end, c.checksum) for c in c1]
    sig2 = [(c.start, c.end, c.checksum) for c in c2]
    assert sig1 == sig2
