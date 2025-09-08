from contract_review_app.intake.normalization import normalize_for_intake


def test_smart_quotes_and_nbsp() -> None:
    text = "“Hello”\u00a0world\t!"
    assert normalize_for_intake(text) == '"Hello" world !'


def test_crlf_to_lf_preserved_linebreaks() -> None:
    text = "Line1\r\nLine2\rLine3\n"
    assert normalize_for_intake(text) == "Line1\nLine2\nLine3\n"
