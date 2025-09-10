import copy

import pytest
from pydantic import ValidationError

from contract_review_app.rules_v2.i18n import resolve_locale
from contract_review_app.rules_v2.models import FindingV2


# ---------------------------------------------------------------------------
# Validation behaviour
# ---------------------------------------------------------------------------


def test_missing_en_raises():
    with pytest.raises(ValidationError):
        FindingV2(
            rule_id="r1",
            title={"uk": "t"},
            message={"en": "m"},
            explain={"en": "e"},
            suggestion={"en": "s"},
        )


def test_extra_keys_and_value_types():
    # extra keys tolerated
    f = FindingV2(
        rule_id="r1",
        title={"en": "t", "fr": "tfr"},
        message={"en": "m"},
        explain={"en": "e"},
        suggestion={"en": "s"},
    )
    assert f.title["fr"] == "tfr"

    # non-string values rejected
    with pytest.raises(ValidationError):
        FindingV2(
            rule_id="r1",
            title={"en": "t", "fr": 1},
            message={"en": "m"},
            explain={"en": "e"},
            suggestion={"en": "s"},
        )


# ---------------------------------------------------------------------------
# resolve_locale behaviour
# ---------------------------------------------------------------------------


def test_resolve_locale():
    assert resolve_locale({"en": "hi"}, prefer="uk") == "hi"
    assert resolve_locale({"en": "hi", "uk": "привіт"}, prefer="uk") == "привіт"
    assert resolve_locale({"en": "hi", "uk": ""}, prefer="uk") == "hi"


# ---------------------------------------------------------------------------
# FindingV2.localize
# ---------------------------------------------------------------------------


def test_localize_fallback_and_stability():
    base = {
        "title": {"en": "Title"},
        "message": {"en": "Message"},
        "explain": {"en": "Explain"},
        "suggestion": {"en": "Suggestion"},
    }
    f = FindingV2(rule_id="r1", **base)
    before = copy.deepcopy(f.dict())

    loc = f.localize(prefer="uk")
    assert loc == {k: v["en"] for k, v in base.items()}
    assert f.dict() == before  # no mutation


def test_localize_prefer_uk():
    base = {
        "title": {"en": "Title", "uk": "Заголовок"},
        "message": {"en": "Message", "uk": "Повідомлення"},
        "explain": {"en": "Explain", "uk": "Пояснення"},
        "suggestion": {"en": "Suggestion", "uk": "Порада"},
    }
    f = FindingV2(rule_id="r1", **base)
    loc = f.localize(prefer="uk")
    assert loc == {k: v["uk"] for k, v in base.items()}
    # deterministic
    assert loc == f.localize(prefer="uk")


def test_has_locale():
    f = FindingV2(
        rule_id="r1",
        title={"en": "Title", "uk": "Заголовок"},
        message={"en": "Message", "uk": "Повідомлення"},
        explain={"en": "Explain", "uk": "Пояснення"},
        suggestion={"en": "Suggestion", "uk": "Порада"},
    )
    assert f.has_locale("uk")
    assert not f.has_locale("fr")
