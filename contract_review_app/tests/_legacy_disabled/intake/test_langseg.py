import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contract_review_app.intake.langseg import (  # noqa: E402
    detect_script,
    script_to_lang,
    segment_lang_script,
)


def assert_invariants(text: str, segs):
    last_end = 0
    rebuilt = []
    for seg in segs:
        start = seg["start"]
        end = seg["end"]
        assert 0 <= start < end <= len(text)
        assert start == last_end
        rebuilt.append(text[start:end])
        last_end = end
    assert last_end == len(text)
    assert "".join(rebuilt) == text


def test_basic_single_scripts():
    cases = [
        ("Hello", "Latin", "en"),
        ("Привіт", "Cyrillic", "uk"),
        ("γειά", "Greek", "el"),
        ("שלום", "Hebrew", "he"),
        ("مرحبا", "Arabic", "ar"),
    ]
    for text, script, lang in cases:
        segs = segment_lang_script(text)
        assert segs == [{"start": 0, "end": len(text), "script": script, "lang": lang}]
        assert_invariants(text, segs)


def test_mixed_scripts():
    text = "Hello Привіт"
    segs = segment_lang_script(text)
    expected = [
        {"start": 0, "end": 5, "script": "Latin", "lang": "en"},
        {"start": 5, "end": 6, "script": "Common", "lang": "und"},
        {"start": 6, "end": len(text), "script": "Cyrillic", "lang": "uk"},
    ]
    assert segs == expected
    assert_invariants(text, segs)


def test_mixed_scripts_complex():
    text = "AβΓ Привіт!"
    segs = segment_lang_script(text)
    expected = [
        {"start": 0, "end": 1, "script": "Latin", "lang": "en"},
        {"start": 1, "end": 3, "script": "Greek", "lang": "el"},
        {"start": 3, "end": 4, "script": "Common", "lang": "und"},
        {"start": 4, "end": 10, "script": "Cyrillic", "lang": "uk"},
        {"start": 10, "end": 11, "script": "Common", "lang": "und"},
    ]
    assert segs == expected
    assert_invariants(text, segs)


def test_common_only():
    text = "12345 !!! 👍"
    segs = segment_lang_script(text)
    assert segs == [{"start": 0, "end": len(text), "script": "Common", "lang": "und"}]
    assert_invariants(text, segs)


def test_merging_logic():
    text = "Hello!!"
    segs = segment_lang_script(text)
    expected = [
        {"start": 0, "end": 5, "script": "Latin", "lang": "en"},
        {"start": 5, "end": len(text), "script": "Common", "lang": "und"},
    ]
    assert segs == expected
    assert_invariants(text, segs)

    text2 = "Hi  there"
    segs2 = segment_lang_script(text2)
    expected2 = [
        {"start": 0, "end": 2, "script": "Latin", "lang": "en"},
        {"start": 2, "end": 4, "script": "Common", "lang": "und"},
        {"start": 4, "end": len(text2), "script": "Latin", "lang": "en"},
    ]
    assert segs2 == expected2
    assert_invariants(text2, segs2)


def test_edge_cases_common_chars():
    text = "A\u200d👍B"  # contains ZWJ and emoji
    segs = segment_lang_script(text)
    expected = [
        {"start": 0, "end": 1, "script": "Latin", "lang": "en"},
        {"start": 1, "end": 3, "script": "Common", "lang": "und"},
        {"start": 3, "end": 4, "script": "Latin", "lang": "en"},
    ]
    assert segs == expected
    assert_invariants(text, segs)


def test_detect_script_basic():
    assert detect_script("A") == "Latin"
    assert detect_script("Ж") == "Cyrillic"
    assert detect_script("β") == "Greek"
    assert detect_script("ش") == "Arabic"
    assert detect_script("ש") == "Hebrew"
    assert detect_script("1") == "Common"


def test_script_to_lang_mapping_total():
    scripts = ["Latin", "Cyrillic", "Greek", "Arabic", "Hebrew", "Common"]
    for script in scripts:
        assert script_to_lang(script) in {"en", "uk", "el", "ar", "he", "und"}
