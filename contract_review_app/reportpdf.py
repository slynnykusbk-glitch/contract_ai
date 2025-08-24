# tests/report/test_pdf_coverage_unit.py
from pathlib import Path
import sys
import types
import shutil
import subprocess
import pytest

# Ми тестуємо модуль report/pdf.py зсередини пакету "report"
from report.renderer import render_html

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
        "text": "Text",
        "law_reference": ["Ref"],
        "anchors": {},
    }
]


def _fake_min_pdf(out: Path):
    out.write_bytes(b"%PDF-1.4\n%%EOF\n")


def test_pdf_auto_prefers_weasyprint_when_present(tmp_path, monkeypatch):
    # 1) Підкладаємо фейковий модуль weasyprint з HTML.write_pdf, що створює файл
    fake_mod = types.ModuleType("weasyprint")

    class FakeHTML:
        def __init__(self, *a, **k):
            pass

        def write_pdf(self, target: str):
            _fake_min_pdf(Path(target))

    fake_mod.HTML = FakeHTML
    sys.modules["weasyprint"] = fake_mod

    # 2) Імпортуємо тільки зараз, щоб підхопився наш sys.modules
    from report.pdf import to_pdf

    html = render_html(SAMPLE, {"theme": "light", "lang": "en", "asset_root": "."})
    out_pdf = tmp_path / "auto_weasy.pdf"
    res = to_pdf(html, out_pdf, asset_root=".", backend="auto")
    assert res.exists() and res.stat().st_size > 0

    # 3) Приберемо модуль, щоб інші тести не думали, що він існує
    del sys.modules["weasyprint"]


def test_pdf_auto_falls_back_to_wkhtmltopdf(tmp_path, monkeypatch):
    # 1) Імітуємо відсутність weasyprint
    if "weasyprint" in sys.modules:
        del sys.modules["weasyprint"]

    # 2) Підміняємо shutil.which, щоб "знайшовся" wkhtmltopdf
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "C:/fake/path/wkhtmltopdf.exe" if name == "wkhtmltopdf" else None,
    )

    # 3) Підміняємо subprocess.run: повертаємо code=0 і створюємо цільовий PDF
    def fake_run(cmd, capture_output=True, text=True):
        # останній аргумент у списку — шлях виводу
        out_path = Path(cmd[-1])
        _fake_min_pdf(out_path)

        class R:
            returncode = 0
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    from report.pdf import to_pdf

    html = render_html(SAMPLE, {"theme": "light", "lang": "en", "asset_root": "."})
    out_pdf = tmp_path / "auto_wk.pdf"
    res = to_pdf(html, out_pdf, asset_root=".", backend="auto")
    assert res.exists() and res.stat().st_size > 0


def test_pdf_wkhtmltopdf_missing_raises(tmp_path, monkeypatch):
    # Вимикаємо weasyprint, імітуємо відсутній wkhtmltopdf
    if "weasyprint" in sys.modules:
        del sys.modules["weasyprint"]
    monkeypatch.setattr(shutil, "which", lambda name: None)

    from report.pdf import to_pdf

    html = "<html><body>Hi</body></html>"
    out_pdf = tmp_path / "no_wk.pdf"

    with pytest.raises(RuntimeError):
        to_pdf(html, out_pdf, asset_root=".", backend="wkhtmltopdf")


def test_pdf_backend_none_raises(tmp_path):
    from report.pdf import to_pdf

    html = "<html><body>Hi</body></html>"
    out_pdf = tmp_path / "no.pdf"
    # Викликаємо через backend="none" опосередковано: to_pdf має кинути RuntimeError
    with pytest.raises(RuntimeError):
        to_pdf(html, out_pdf, asset_root=".", backend="none")
