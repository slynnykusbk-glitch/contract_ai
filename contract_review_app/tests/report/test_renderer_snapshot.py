import re
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
        "clause_type": "Liability",
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


def test_render_light_contains_badges_and_summary(tmp_path):
    html = render_html(SAMPLE, {"theme": "light", "lang": "en", "asset_root": tmp_path})
    # Перевіримо наявність бейджів та summary полів
    assert "badge-ok" in html
    assert "badge-warn" in html
    assert "badge-fail" in html
    assert re.search(r"Summary|overview", html, re.IGNORECASE)


def test_render_dark_theme(tmp_path):
    html = render_html(SAMPLE, {"theme": "dark", "lang": "en", "asset_root": tmp_path})
    # Тест на якір і заголовки
    assert 'id="clause-1"' in html
    assert "Governing Law" in html


def test_render_ukrainian_language(tmp_path):
    from contract_review_app.report.renderer import render_html

    sample = [
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
            "text": "...",
            "law_reference": [],
            "anchors": {},
        }
    ]
    html = render_html(sample, {"theme": "light", "lang": "uk", "asset_root": tmp_path})
    assert "Звіт аналізу договору" in html  # заголовок
    assert "Зведення" in html  # панель summary
    assert 'class="badge badge-ok"' in html


def test_render_contains_toc(tmp_path):
    from contract_review_app.report.renderer import render_html

    html = render_html(SAMPLE, {"theme": "light", "lang": "en", "asset_root": "."})
    assert "Contents" in html
    assert '<a href="#clause-1">' in html
