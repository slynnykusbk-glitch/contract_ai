#!/usr/bin/env python
from __future__ import annotations
import json
import sys
import argparse
import logging
from pathlib import Path
from typing import Any, List, Dict

from contract_review_app.report.renderer import render_html
from contract_review_app.report.pdf import to_pdf

logger = logging.getLogger("diag_report")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _load_json(json_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON must contain a list of AnalysisOutput objects")
    return data


def main() -> int:
    p = argparse.ArgumentParser(
        description="Diagnostic: JSON AnalysisOutput[] -> HTML/PDF preview"
    )
    p.add_argument(
        "--json",
        dest="jsonfile",
        type=Path,
        required=True,
        help="Input JSON (AnalysisOutput[])",
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
    args = p.parse_args()

    try:
        results = _load_json(args.jsonfile)
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

        if args.pdf_out:
            to_pdf(html, args.pdf_out, asset_root=args.asset_root, backend=args.backend)
            logger.info("PDF saved: %s", args.pdf_out)
        return 0
    except FileNotFoundError as e:
        logger.error("I/O error: %s", e)
        return 4
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
