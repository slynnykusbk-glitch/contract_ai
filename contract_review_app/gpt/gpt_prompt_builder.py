# contract_review_app/gpt/gpt_prompt_builder.py
# ASCII-only. Prompt builder with modes and guard constraints.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


# ------------------------------ public API ----------------------------------

@dataclass
class PromptParts:
    system: str
    user: str


def build_gpt_prompt(
    analysis: Union[Dict[str, Any], Any, str],
    mode: str = "friendly",
    max_findings: int = 8,
    max_clause_chars: int = 1800,
    max_prompt_chars: int = 8000,
) -> PromptParts:
    """
    Build a deterministic system+user prompt for the drafting LLM.
    - Accepts AnalysisOutput-like dict/object or raw clause text (str).
    - Modes: friendly | standard | strict (stylistic constraints only).
    - No external sources are allowed beyond analysis.citations.
    - Returns PromptParts(system, user).
    """
    a = _normalize_analysis(analysis)
    allowed_sources = _extract_allowed_sources(a.get("citations") or [])
    findings = _select_top_findings(a.get("findings") or [], max_findings=max_findings)
    clause_type = (a.get("clause_type") or "clause").strip()
    status = (a.get("status") or "").strip() or "OK"
    risk = (a.get("risk") or a.get("risk_level") or a.get("severity") or "medium").strip()
    base_text = (a.get("proposed_text") or a.get("text") or "").strip()
    base_text = base_text[:max_clause_chars]

    system = _system_preamble(mode=mode, allowed_sources=allowed_sources)

    user_lines: List[str] = []
    user_lines.append(f"Task: draft a clean, production-ready {clause_type} text for a UK/International contract.")
    user_lines.append("Do not include markdown. Return only the clause text, no meta or disclaimers.")
    user_lines.append("")
    user_lines.append("Context:")
    user_lines.append(f"- Clause type: {clause_type}")
    user_lines.append(f"- Current status: {status}")
    user_lines.append(f"- Risk level: {risk}")

    if findings:
        user_lines.append("- Top findings to address:")
        for f in findings:
            code = f.get("code") or ""
            msg = (f.get("message") or "").strip()
            if not msg:
                continue
            user_lines.append(f"  * [{code}] {msg}")

    if allowed_sources:
        user_lines.append("- Allowed legal sources (may reference only these, if needed):")
        for s in sorted(allowed_sources):
            user_lines.append(f"  * {s}")

    if base_text:
        user_lines.append("")
        user_lines.append("Original Clause:")
        user_lines.append(base_text)

    user_lines.append("")
    user_lines.append(_mode_constraints_block(mode))

    # final clamp and join
    user = _clamp("\n".join(user_lines).strip(), max_prompt_chars)
    return PromptParts(system=_clamp(system, max_prompt_chars), user=user)


# Back-compat: legacy name expected by some callers.
def build_prompt(
    analysis: Union[Dict[str, Any], Any, str],
    mode: str = "friendly",
    **kwargs: Any,
) -> Dict[str, str]:
    pp = build_gpt_prompt(analysis=analysis, mode=mode, **kwargs)
    return {"system": pp.system, "user": pp.user}


# Utility for simple single-string APIs (optional).
def build_prompt_text(
    analysis: Union[Dict[str, Any], Any, str],
    mode: str = "friendly",
    **kwargs: Any,
) -> str:
    pp = build_gpt_prompt(analysis=analysis, mode=mode, **kwargs)
    return f"[SYSTEM]\n{pp.system}\n\n[USER]\n{pp.user}"


# ------------------------------ internals -----------------------------------

_SEV_ORDER = {
    "info": 0,
    "minor": 1,
    "medium": 1,
    "major": 2,
    "high": 2,
    "critical": 3,
}

def _normalize_analysis(analysis: Union[Dict[str, Any], Any, str]) -> Dict[str, Any]:
    if isinstance(analysis, str):
        return {"clause_type": "clause", "status": "OK", "risk": "medium", "text": analysis, "findings": [], "citations": []}
    if isinstance(analysis, dict):
        return dict(analysis)
    # object with attributes (pydantic model or similar)
    out: Dict[str, Any] = {}
    for k in ("clause_type", "status", "risk", "risk_level", "severity", "text", "proposed_text", "findings", "citations"):
        out[k] = getattr(analysis, k, None)
    return out


def _extract_allowed_sources(citations: Iterable[Any]) -> List[str]:
    res: List[str] = []
    for c in citations or []:
        try:
            inst = (c.get("instrument") if isinstance(c, dict) else getattr(c, "instrument", None)) or ""
            sec = (c.get("section") if isinstance(c, dict) else getattr(c, "section", None)) or ""
            if inst or sec:
                res.append(f"{inst} {sec}".strip())
        except Exception:
            continue
    # unique, keep order of first occurrence
    seen = set()
    uniq: List[str] = []
    for s in res:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _sev_ord(v: Optional[str]) -> int:
    if not v:
        return 1
    return _SEV_ORDER.get(str(v).lower().strip(), 1)


def _select_top_findings(findings: Iterable[Any], max_findings: int = 8) -> List[Dict[str, Any]]:
    buf: List[Tuple[int, Dict[str, Any]]] = []
    for f in findings or []:
        try:
            code = (f.get("code") if isinstance(f, dict) else getattr(f, "code", "")) or ""
            msg = (f.get("message") if isinstance(f, dict) else getattr(f, "message", "")) or ""
            sev = (f.get("severity") if isinstance(f, dict) else getattr(f, "severity", "")) or \
                  (f.get("severity_level") if isinstance(f, dict) else getattr(f, "severity_level", "")) or ""
            ordv = _sev_ord(sev)
            item = {"code": code, "message": msg, "severity": sev}
            buf.append((ordv, item))
        except Exception:
            continue
    # sort by severity desc, preserve stable order within same severity
    buf.sort(key=lambda t: t[0], reverse=True)
    return [x for _, x in buf[:max_findings]]


def _mode_constraints_block(mode: str) -> str:
    m = (mode or "friendly").strip().lower()
    if m not in ("friendly", "standard", "strict"):
        m = "friendly"
    if m == "friendly":
        return (
            "Style constraints (friendly):\n"
            "- Use clear, concise business language.\n"
            "- Prefer 'should' where appropriate; avoid over-formal tone.\n"
            "- Keep obligations balanced; avoid unnecessary rigidity."
        )
    if m == "standard":
        return (
            "Style constraints (standard):\n"
            "- Use precise drafting; use 'shall' for obligations.\n"
            "- Include notice/cure, timeframes, and standard carve-outs.\n"
            "- Avoid ambiguity; align with common UK practice."
        )
    # strict
    return (
        "Style constraints (strict):\n"
        "- Use firm obligations ('shall'), explicit timelines, and clear remedies.\n"
        "- Close loopholes; define terms if needed for precision.\n"
        "- Keep text enforceable and audit-ready."
    )


def _system_preamble(mode: str, allowed_sources: List[str]) -> str:
    # Guard constraints to prevent hallucinated sources and meta content.
    lines: List[str] = []
    lines.append("You are a contract drafting assistant.")
    lines.append("Return only the clause text. Do not include markdown, explanations, or disclaimers.")
    lines.append("Do not invent legal sources. If you reference a legal instrument or section, it must be from the allowed list.")
    lines.append("Do not contradict high-severity findings; address them with appropriate protections.")
    lines.append("Do not change the meaning of allowed sources; you may rephrase but not miscite.")
    if allowed_sources:
        lines.append("Allowed sources:")
        for s in sorted(set(allowed_sources)):
            lines.append(f"- {s}")
    lines.append(f"Drafting mode: {mode.lower().strip() if mode else 'friendly'}")
    return "\n".join(lines)


def _clamp(s: str, n: int) -> str:
    if not s:
        return s
    if len(s) <= n:
        return s
    return s[:n]
