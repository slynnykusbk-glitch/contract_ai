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
        "text": "Gov law text",
        "law_reference": [],
        "anchors": {},
    }
]


def test_render_email_minimal_smoke(tmp_path):
    html = render_html(SAMPLE, {"lang": "uk", "email_minimal": True, "asset_root": "."})
    # базові перевірки контенту
    assert "Звіт аналізу договору" in html
    assert "Зведення" in html
    assert 'id="clause-1"' in html
    assert "OK" in html or "ОК" in html
    # має бути вбудована таблиця-обгортка, без складних класів
    assert "<table" in html and "</table>" in html
