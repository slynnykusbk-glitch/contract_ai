"""Simple prompt builder for GPT drafting.

This module exposes :func:`build_prompt`, which returns a single string
combining all sections needed for the LLM.  It accepts either a Pydantic
``AnalysisOutput`` model or a plain ``dict`` containing the same keys.
The function is intentionally lightweight and deterministic so it can be
used in tests without accessing external services.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .prompt_builder_utils import _diag_to_str


def _normalize_analysis(analysis: Any) -> Dict[str, Any]:
    """Return a dict representation of ``analysis``.

    If the object provides ``model_dump`` (Pydantic v2) it is used, otherwise
    ``analysis`` is returned as-is when it's already a ``dict``.  Fallback to an
    empty dict for unsupported types so callers never receive ``None``.
    """

    if hasattr(analysis, "model_dump"):
        try:
            return analysis.model_dump()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            return {}
    if isinstance(analysis, dict):
        return dict(analysis)
    return {}


def _as_iter(value: Any) -> List[Any]:
    """Coerce ``value`` into a list for iteration."""

    if value is None:
        return []
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def build_prompt(analysis: Any) -> str:
    """Build a single string prompt from ``analysis``.

    The output layout is:

    ``[SYSTEM]`` – fixed system instructions.
    ``[HEADER]`` – clause type and status.
    ``[FINDINGS]`` – optional bullet list ``- [severity] message``.
    ``[RECOMMENDATIONS]`` – optional bullet list of recommendations.
    ``[DIAGNOSTICS]`` – optional bullet list derived from diagnostics.
    ``[ORIGINAL]`` – the original clause text.
    """

    a = _normalize_analysis(analysis)

    clause_type = str(a.get("clause_type") or "Clause").strip()
    status = str(a.get("status") or "UNKNOWN").strip()
    original_text = str(a.get("text") or "").strip()

    sections: List[str] = []

    system_rules = (
        "[SYSTEM]\n"
        "Return only the clause text. Use UK law. Ensure clarity. "
        "No markdown or comments."
    )
    sections.append(system_rules)

    header = f"[HEADER]\nClause Type: {clause_type}\nStatus: {status}"
    sections.append(header)

    # Findings
    finding_lines: List[str] = []
    for f in _as_iter(a.get("findings")):
        if isinstance(f, dict):
            sev = f.get("severity") or f.get("severity_level") or "info"
            msg = f.get("message") or ""
        else:
            sev = (
                getattr(f, "severity", "") or getattr(f, "severity_level", "") or "info"
            )
            msg = getattr(f, "message", "") or ""
        msg = str(msg).strip()
        sev = str(sev or "info").strip().lower()
        if msg:
            finding_lines.append(f"- [{sev}] {msg}")
    if finding_lines:
        sections.append("[FINDINGS]\n" + "\n".join(finding_lines))

    # Recommendations
    rec_lines = [f"- {str(r)}" for r in _as_iter(a.get("recommendations")) if str(r)]
    if rec_lines:
        sections.append("[RECOMMENDATIONS]\n" + "\n".join(rec_lines))

    # Diagnostics
    diag_lines = [
        f"- {_diag_to_str(d)}"
        for d in _as_iter(a.get("diagnostics"))
        if _diag_to_str(d)
    ]
    if diag_lines:
        sections.append("[DIAGNOSTICS]\n" + "\n".join(diag_lines))

    if original_text:
        sections.append("[ORIGINAL]\n" + original_text)

    return "\n\n".join(sections).strip()


# ---------------------------------------------------------------------------
# Compatibility helpers retained for callers expecting previous APIs
# ---------------------------------------------------------------------------


def build_prompt_text(analysis: Any, *_, **__) -> str:
    """Alias returning the single-string prompt."""

    return build_prompt(analysis)


def build_prompt_parts(analysis: Any, *_, **__) -> Dict[str, str]:
    """Return a dict with a single ``prompt`` key for compatibility."""

    return {"prompt": build_prompt(analysis)}


def build_gpt_prompt(analysis: Any, *_, **__) -> Dict[str, str]:
    """Backward-compatible placeholder returning the same string."""

    return build_prompt_parts(analysis)
