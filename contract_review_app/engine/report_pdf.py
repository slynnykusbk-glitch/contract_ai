from __future__ import annotations

from typing import Any


def html_to_pdf(html: str) -> bytes:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as ex:  # pragma: no cover - optional dependency
        raise NotImplementedError("PDF export not enabled") from ex
    return HTML(string=html).write_pdf()
