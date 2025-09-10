import pytest
from contract_review_app.intake.text_cleaning import (
    normalize_whitespace,
    remove_control_characters,
    clean_punctuation_spacing,
    remove_artifacts_and_garbage,
    preprocess_text,
)


def test_normalize_whitespace():
    assert normalize_whitespace("Hello   world") == "Hello world"
    assert normalize_whitespace("line1\n\n\nline2") == "line1\n\nline2"


def test_remove_control_characters():
    text_with_ctrl = "Hello\x0cWorld"
    assert remove_control_characters(text_with_ctrl) == "HelloWorld"


def test_clean_punctuation_spacing():
    assert clean_punctuation_spacing("Hello ,world") == "Hello, world"
    assert clean_punctuation_spacing("Test.abc") == "Test. abc"


def test_remove_artifacts_and_garbage():
    assert remove_artifacts_and_garbage("¡×}Hello") == "Hello"
    assert remove_artifacts_and_garbage("Hello*") == "Hello"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Hello   ,world¡×", "Hello, world"),
        ("Test\\x90string", "Test string"),
        ("line1\n\n\nline2", "line1\n\nline2"),
    ],
)
def test_preprocess_text_property(raw, expected):
    assert preprocess_text(raw) == expected
