import re
import pytest
from contract_review_app.report.renderer import render_html

SAMPLE = [
    {
        "clause_id": "1",
        "clause_type": "Governing Law",
        "title": "Governing Law",
        "status": "OK",
        "score": 95,
        "risk_level": "low",
        "severity": "info",
        "problems": [],
        "recommendations": [],
        "text": "This Agreement is governed by the laws of England and Wales.",
        "law_reference": ["Rome I Regulation"],
        "anchors": {},
    },
    {
        "clause_id": "2",
        "clause_type": "Indemnity",
        "title": "Indemnity",
        "status": "WARN",
        "score": 70,
        "risk_level": "medium",
        "severity": "warn",
        "problems": ["Carve-outs missing"],
        "recommendations": ["Add cap and carve-outs"],
        "text": "Supplier shall indemnify...",
        "law_reference": [],
        "anchors": {},
    },
    {
        "clause_id": "3",
        "clause_type": "Limitation of Liability",
        "title": "Limitation of Liability",
        "status": "FAIL",
        "score": 30,
        "risk_level": "high",
        "severity": "critical",
        "problems": ["Unlimited liability detected"],
        "recommendations": ["Introduce reasonable cap"],
        "text": "Liability is unlimited...",
        "law_reference": [],
        "anchors": {},
    },
]


@pytest.mark.parametrize(
    "theme,lang,email_min",
    [
        ("light", "en", False),
        ("dark", "en", False),
        ("light", "uk", False),
        ("dark", "uk", False),
        ("light", "en", True),  # email-minimal (без тем)
    ],
)
def test_renderer_snapshots(theme, lang, email_min, file_regression):
    settings = {
        "theme": theme,
        "lang": lang,
        "email_minimal": email_min,
        "asset_root": ".",
    }
    html = render_html(SAMPLE, settings)

    # стабілізатор: прибираємо потенційні пробіли на кінцях рядків
    html = "\n".join([line.rstrip() for line in html.splitlines()])

    suffix = f"{theme}_{lang}_{'email' if email_min else 'full'}"
    file_regression.check(html, extension=f".{suffix}.html")


def test_basic_validity_light_en():
    html = render_html(SAMPLE, {"theme": "light", "lang": "en", "asset_root": "."})
    assert "<!doctype html>" in html.lower()
    assert 'id="clause-1"' in html
    assert re.search(r"Summary|overview|Зведення", html, re.IGNORECASE)


def test_basic_validity_email_uk():
    html = render_html(SAMPLE, {"email_minimal": True, "lang": "uk", "asset_root": "."})
    assert "<table" in html and "</table>" in html
    assert "Звіт аналізу договору" in html
    assert 'id="clause-1"' in html
