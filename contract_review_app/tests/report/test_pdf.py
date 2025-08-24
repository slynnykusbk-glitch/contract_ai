import shutil
import pytest

from contract_review_app.report.renderer import render_html
from contract_review_app.report.pdf import to_pdf


def _pdf_backend_available() -> bool:
    # 1) перевірка weasyprint без фатального імпорту
    try:
        import importlib

        importlib.import_module("weasyprint")
        return True
    except Exception:
        pass
    # 2) перевірка wkhtmltopdf у PATH
    return shutil.which("wkhtmltopdf") is not None


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
    }
]


@pytest.mark.skipif(
    not _pdf_backend_available(),
    reason="No PDF backend (weasyprint/wkhtmltopdf) available",
)
def test_pdf_generation_smoke(tmp_path):
    html = render_html(SAMPLE, {"theme": "light", "lang": "en", "asset_root": "."})
    out_file = tmp_path / "report.pdf"
    pdf_path = to_pdf(html, out_file, asset_root=".", backend="auto")
    assert pdf_path.exists(), "PDF file was not created"
    assert pdf_path.stat().st_size > 0, "PDF file is empty"


@pytest.mark.skipif(
    not _pdf_backend_available(),
    reason="No PDF backend (weasyprint/wkhtmltopdf) available",
)
def test_pdf_generation_with_custom_asset_root(tmp_path):
    html = "<html><head><style>body{font-family: sans-serif;}</style></head><body><h1>Test</h1></body></html>"
    out_file = tmp_path / "custom.pdf"
    pdf_path = to_pdf(html, out_file, asset_root=tmp_path, backend="auto")
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
