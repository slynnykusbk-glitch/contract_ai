from __future__ import annotations
from pathlib import Path
from typing import Optional, Literal
import logging
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

PDFBackend = Literal["auto", "weasyprint", "wkhtmltopdf", "none"]


def _resolve_base_url(asset_root: Optional[str | Path]) -> str:
    if asset_root:
        return str(Path(asset_root).resolve())
    return str((Path(__file__).parent / "templates").resolve())


def _weasyprint_available() -> bool:
    try:
        import weasyprint  # noqa: F401

        return True
    except Exception:
        return False


def _wkhtmltopdf_available() -> bool:
    return shutil.which("wkhtmltopdf") is not None


def _to_pdf_weasyprint(html: str, out_path: Path, base_url: str) -> None:
    from weasyprint import HTML

    HTML(string=html, base_url=base_url).write_pdf(target=str(out_path))


def _to_pdf_wkhtmltopdf(html: str, out_path: Path, base_url: str) -> None:
    # Зберігаємо тимчасовий HTML (з base_url як директорія для відносних ресурсів)
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        temp_html = temp_dir / "report.html"
        temp_html.write_text(html, encoding="utf-8")
        # Викликаємо wkhtmltopdf
        cmd = ["wkhtmltopdf", str(temp_html), str(out_path)]
        logger.info("Running wkhtmltopdf: %s", " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error("wkhtmltopdf failed: %s", res.stderr[:5000])
            raise RuntimeError(f"wkhtmltopdf failed with code {res.returncode}")


def to_pdf(
    html: str,
    out_path: str | Path,
    asset_root: Optional[str | Path] = None,
    backend: PDFBackend = "auto",
) -> Path:
    """
    Генерує PDF офлайн з HTML.
    backend:
      - "auto": спробувати weasyprint, якщо недоступний — wkhtmltopdf
      - "weasyprint": змусити weasyprint
      - "wkhtmltopdf": змусити wkhtmltopdf
      - "none": не генерувати PDF (кинути виняток)
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    base_url = _resolve_base_url(asset_root)

    chosen = backend
    if backend == "auto":
        if _weasyprint_available():
            chosen = "weasyprint"
        elif _wkhtmltopdf_available():
            chosen = "wkhtmltopdf"
        else:
            chosen = "none"

    logger.info("PDF backend: %s (base_url=%s)", chosen, base_url)

    if chosen == "weasyprint":
        try:
            _to_pdf_weasyprint(html, out, base_url)
        except Exception as e:
            logger.warning("WeasyPrint failed: %s", e)
            if backend == "auto" and _wkhtmltopdf_available():
                logger.info("Falling back to wkhtmltopdf...")
                _to_pdf_wkhtmltopdf(html, out, base_url)
            else:
                raise
    elif chosen == "wkhtmltopdf":
        if not _wkhtmltopdf_available():
            raise RuntimeError(
                "wkhtmltopdf not found in PATH. Install it or use backend=weasyprint."
            )
        _to_pdf_wkhtmltopdf(html, out, base_url)
    else:
        raise RuntimeError(
            "No PDF backend available. Install 'weasyprint' or 'wkhtmltopdf', "
            "or set backend='none' and skip PDF generation."
        )

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("PDF generation failed: output file missing or empty.")
    logger.info("PDF generated: %s (%d bytes)", out, out.stat().st_size)
    return out
