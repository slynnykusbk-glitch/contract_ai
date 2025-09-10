from contract_review_app.intake.splitter import split_into_candidate_blocks


def test_split_on_double_newline():
    raw = "Clause A line 1.\n\nClause B line 1."
    out = split_into_candidate_blocks(raw, min_len=20, sentence_split_over=200)
    assert len(out) == 2
    assert "Clause A" in out[0]
    assert "Clause B" in out[1]


def test_split_on_numbered_items():
    raw = "1. Definitions\nText A.\n2. Term\nText B."
    out = split_into_candidate_blocks(raw, min_len=10, sentence_split_over=200)
    # Заголовок + текст мають злитися разом у 2 блоки
    assert len(out) == 2
    assert "1. Definitions" in out[0]
    assert "Text A." in out[0]
    assert "2. Term" in out[1]
    assert "Text B." in out[1]


def test_alpha_list_items():
    raw = "a) First point\nText A.\n\nb) Second point\nText B."
    out = split_into_candidate_blocks(raw, min_len=10, sentence_split_over=200)
    assert len(out) == 2
    assert "a) First point" in out[0] and "Text A." in out[0]
    assert "b) Second point" in out[1] and "Text B." in out[1]


def test_merge_short_heading_with_text():
    raw = "TERMINATION\nThe contract may be terminated..."
    out = split_into_candidate_blocks(raw, min_len=40, sentence_split_over=200)
    assert len(out) == 1
    assert "TERMINATION\nThe contract" in out[0]


def test_merge_broken_sentences_lowercase_next():
    raw = "This obligation shall survive termination\napplies to both parties."
    out = split_into_candidate_blocks(raw, min_len=10, sentence_split_over=200)
    assert len(out) == 1
    assert "survive termination applies to both parties" in out[0]


def test_sentence_split_for_very_long_paragraph():
    long_sent = (
        "This is a long sentence. Another sentence follows. Final sentence here."
    )
    raw = long_sent * 10  # робимо блок довшим за поріг
    out = split_into_candidate_blocks(raw, min_len=10, sentence_split_over=50)
    # має розбитися на речення
    assert len(out) >= 3


def test_filter_noise_short_blocks_do_not_remain():
    raw = "A\n\nB\n\nValid block with enough length to pass."
    out = split_into_candidate_blocks(raw, min_len=25, sentence_split_over=200)
    # короткі A/B мають злитися/зникнути, має лишитися хоч один валідний блок
    assert any("Valid block" in b for b in out)
