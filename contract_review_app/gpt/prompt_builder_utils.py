# 📄 contract_review_app/gpt/prompt_builder_utils.py
from __future__ import annotations
import json
from typing import Any
from contract_review_app.core.schemas import AnalysisOutput


def _diag_to_str(d: Any) -> str:
    """
    Coerce a diagnostic item to a readable string.
    Accepts str | dict | pydantic model | generic object.
    """
    try:
        if isinstance(d, str):
            return d
        if isinstance(d, dict):
            code = d.get("code") or d.get("rule") or d.get("id") or ""
            msg = (
                d.get("message")
                or d.get("detail")
                or d.get("reason")
                or d.get("text")
                or ""
            )
            if code and msg:
                return f"{code}: {msg}"
            if msg:
                return msg
            return json.dumps(d, ensure_ascii=False)
        # pydantic v2 model
        if hasattr(d, "model_dump"):
            return _diag_to_str(d.model_dump())  # type: ignore[attr-defined]
        # generic object: try common attrs
        parts = []
        for attr in (
            "code",
            "message",
            "detail",
            "rule",
            "name",
            "reason",
            "text",
            "info",
        ):
            if hasattr(d, attr):
                val = getattr(d, attr)
                if val:
                    parts.append(str(val))
        return " | ".join(parts) if parts else str(d)
    except Exception:
        return str(d)


def build_prompt(analysis: AnalysisOutput) -> str:
    """
    ✅ Alias: build_prompt_for_clause(analysis)
    Builds a GPT prompt to rewrite a clause based on rule-based analysis results.
    """
    clause_type = analysis.clause_type or "Unknown Clause"
    status = analysis.status or "UNKNOWN"
    recommendations = analysis.recommendations or []
    findings = analysis.findings or []
    diagnostics = analysis.diagnostics or []
    original_text = analysis.text or ""

    explanation = (
        "You are a legal drafting assistant. "
        "Your task is to rewrite the clause below to align with legal standards under UK law, "
        "preserve legal clarity, reduce legal risk, and reflect the provided findings and recommendations. "
        "Do not include any commentary or metadata. Only output the revised clause text.\n"
    )

    header = f"Clause Type: {clause_type}\nStatus: {status}\n\n"

    sev_map = {"minor": "low", "major": "medium", "critical": "high"}
    findings_section = (
        "Findings:\n"
        + "\n".join(
            f"- [{sev_map.get(f.severity or 'info', f.severity or 'info')}] {f.message}"
            for f in findings
        )
        if findings
        else ""
    )

    recommendations_section = (
        "Recommendations:\n" + "\n".join(f"- {r}" for r in recommendations)
        if recommendations
        else ""
    )

    # Safely coerce diagnostics to strings
    _diag_lines = []
    try:
        for d in diagnostics:
            _diag_lines.append(_diag_to_str(d))
    except TypeError:
        # diagnostics may be a dict/single object
        _diag_lines = [_diag_to_str(diagnostics)]
    diagnostics_section = (
        ("Diagnostics:\n" + "\n".join(_diag_lines)) if _diag_lines else ""
    )

    clause_section = f"\n\nOriginal Clause:\n---\n{original_text.strip()}\n---\n"

    prompt = (
        explanation
        + header
        + (findings_section + "\n\n" if findings else "")
        + (recommendations_section + "\n\n" if recommendations else "")
        + (diagnostics_section + "\n\n" if diagnostics else "")
        + clause_section
        + "\nPlease provide the improved clause text only:"
    )

    return prompt.strip()
