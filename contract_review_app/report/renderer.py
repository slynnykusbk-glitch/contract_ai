# contract_review_app/report/renderer.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
import logging
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, select_autoescape
from .metrics import summarize_statuses
from .i18n import get_translator

logger = logging.getLogger(__name__)


def render_html(results: List[Dict[str, Any]], settings: Dict[str, Any]) -> str:
    """
    Pure renderer: AnalysisOutput[] + settings -> HTML string.
    settings: {theme, lang, email_minimal, asset_root}
    """
    theme = settings.get("theme", "light")
    lang = settings.get("lang", "en")
    email_min = bool(settings.get("email_minimal", False))
    asset_root_val = settings.get("asset_root")

    # Якщо не передано asset_root — не заважаємо пошуку пакетних шаблонів
    asset_root = Path(asset_root_val) if asset_root_val else None
    t = get_translator(lang)

    env = _build_env(asset_root)

    # --- RG5: вибір шаблону для e-mail мінімального вигляду ---
    if email_min:
        template_name = "email_minimal.html"
    else:
        template_name = "report_light.html" if theme == "light" else "report_dark.html"

    metrics = summarize_statuses(results)
    view = _to_view_model(results)

    template = env.get_template(template_name)
    html = template.render(t=t, results=view, metrics=metrics, settings=settings)
    return html


def _build_env(asset_root: Path | None) -> Environment:
    """
    Jinja2 loader з кількома пошуковими шляхами:
    1) пакетний шлях: <this_file_dir>/templates
    2) (опц.) asset_root/contract_review_app/report/templates
    """
    package_templates = Path(__file__).parent / "templates"
    search_paths = [str(package_templates)]

    if asset_root:
        candidate = asset_root / "contract_review_app" / "report" / "templates"
        # Додаємо навіть якщо зараз не існує — Jinja просто пропустить
        search_paths.insert(0, str(candidate))

    logger.debug("Jinja2 search paths: %s", search_paths)

    loader = ChoiceLoader([FileSystemLoader(p) for p in search_paths])
    env = Environment(
        loader=loader,
        autoescape=select_autoescape(["html", "xml"]),
        enable_async=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


def _to_view_model(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Map AnalysisOutput -> render-friendly dict (без зміни схем).
    """
    view = []
    for r in results:
        view.append(
            {
                "id": r.get("clause_id") or r.get("id"),
                "type": r.get("clause_type"),
                "title": r.get("title") or r.get("clause_type") or "Clause",
                "status": r.get("status"),
                "score": r.get("score"),
                "risk_level": r.get("risk_level"),
                "severity": r.get("severity"),
                "problems": r.get("problems") or [],
                "recommendations": r.get("recommendations") or [],
                "text": r.get("text") or "",
                "law_reference": r.get("law_reference") or [],
                "anchors": r.get("anchors") or {},
            }
        )
    return view
