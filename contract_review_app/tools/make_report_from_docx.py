#!/usr/bin/env python
from __future__ import annotations
import json
import sys
import argparse
import logging
from pathlib import Path
from typing import Any, List, Dict

# Локальні імпорти
from contract_review_app.report.renderer import render_html

logger = logging.getLogger("make_report")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _load_analysis_from_docx(docx_path: Path) -> List[Dict[str, Any]]:
    """
    Підключення до вашого core-аналізу. Залишено як 'best effort':
    1) Спробувати імпорт вашого пайплайну.
    2) Якщо не вдасться — кинути виняток із підказкою використати --json або --mock.
    """
    try:
        # ПРИКЛАД: адаптуйте під ваш реальний інтерфейс
        from contract_review_app.core.pipeline import analyze_docx  # type: ignore

        return analyze_docx(str(docx_path))
    except Exception as e:
        raise RuntimeError(
            "Cannot import or run core pipeline (contract_review_app.core.pipeline.analyze_docx). "
            "Use --json <file.json> or --mock for demo."
        ) from e


def _load_analysis_from_json(json_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON must contain a list of AnalysisOutput objects")
    return data


def _mock_results() -> List[Dict[str, Any]]:
    return [
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
    ]


def main() -> int:
    p = argparse.ArgumentParser(description="DOCX -> HTML/PDF report generator")
    p.add_argument("--in", dest="infile", type=Path, help="Input DOCX file")
    p.add_argument(
        "--json",
        dest="jsonfile",
        type=Path,
        help="Alternative: JSON with AnalysisOutput[]",
    )
    p.add_argument(
        "--html", dest="html_out", type=Path, required=True, help="Output HTML path"
    )
    p.add_argument(
        "--pdf", dest="pdf_out", type=Path, help="Output PDF path (optional)"
    )
    p.add_argument("--lang", default="en", choices=["en", "uk"], help="Localization")
    p.add_argument(
        "--theme",
        default="light",
        choices=["light", "dark"],
        help="Theme for full HTML",
    )
    p.add_argument(
        "--email-minimal", action="store_true", help="Render email-minimal HTML"
    )
    p.add_argument(
        "--asset-root",
        type=Path,
        default=Path("."),
        help="Asset root (templates/fonts)",
    )
    p.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "weasyprint", "wkhtmltopdf", "none"],
        help="PDF backend",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="Use built-in mock if core pipeline unavailable",
    )
    args = p.parse_args()

    try:
        # 1) Вхідні дані
        results: List[Dict[str, Any]]
        if args.jsonfile and args.jsonfile.exists():
            results = _load_analysis_from_json(args.jsonfile)
        elif args.infile and args.infile.exists():
            try:
                results = _load_analysis_from_docx(args.infile)
            except Exception as e:
                if args.mock:
                    logger.warning("Falling back to --mock due to core error: %s", e)
                    results = _mock_results()
                else:
                    raise
        elif args.mock:
            results = _mock_results()
        else:
            logger.error(
                "No input provided. Use --in <file.docx> or --json <file.json> or --mock."
            )
            return 2

        # 2) Рендер HTML
        settings = {
            "theme": args.theme,
            "lang": args.lang,
            "email_minimal": bool(args.email_minimal),
            "asset_root": str(args.asset_root),
        }
        html = render_html(results, settings)
        args.html_out.parent.mkdir(parents=True, exist_ok=True)
        args.html_out.write_text(html, encoding="utf-8")
        logger.info("HTML saved: %s", args.html_out)

        # 3) Опційно PDF
        if args.pdf_out:
            from contract_review_app.report.pdf import (
                to_pdf,
            )  # already imported above (keep for clarity)

            to_pdf(html, args.pdf_out, asset_root=args.asset_root, backend=args.backend)
            logger.info("PDF saved: %s", args.pdf_out)

        return 0
    except FileNotFoundError as e:
        logger.error("I/O error: %s", e)
        return 4
    except RuntimeError as e:
        logger.error("%s", e)
        if "PDF" in str(e) or "backend" in str(e) or "wkhtmltopdf" in str(e):
            return 3
        return 1
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
