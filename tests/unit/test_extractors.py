import re

from contract_review_app.analysis import extractors as ex


def test_extract_amounts_basic():
    txt = "The Contract Price is £10,000 and an additional USD 2,500 may apply."
    amounts = ex.extract_amounts(txt)
    joined = " ".join(
        " ".join(
            str(part)
            for part in (
                (entry.get("value") or {}).get("currency"),
                (entry.get("value") or {}).get("amount"),
            )
            if part not in (None, "")
        )
        for entry in amounts or []
    )
    assert "10,000" in joined or "10000" in joined
    assert any(token in joined for token in ("USD", "$", "2,500", "2500"))


def test_detect_durations_days_and_business_days():
    samples = [
        "payable within 30 days",
        "no later than 15 days",
        "due within 6 months",
    ]
    ok = 0
    for sample in samples:
        durations = ex.extract_durations(sample)
        if any("duration" in (entry.get("value") or {}) for entry in durations or []):
            ok += 1
    assert ok >= 2


def test_percentages_basic():
    txt = "Service credits: 5% per week capped at 20% of monthly fees."
    percentages = ex.extract_percentages(txt)
    joined = " ".join(
        " ".join(
            str(value)
            for value in (entry.get("value") or {}).values()
            if value not in (None, "")
        )
        for entry in percentages or []
    )
    assert re.search(r"\b(5|20)\b", joined)
