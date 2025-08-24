# contract_review_app/gpt/gpt_proxy_api.py
# ASCII-only. Deterministic mock for GPT drafting with light guardrails.
from __future__ import annotations

from typing import Any, List, Optional

from contract_review_app.core.schemas import AnalysisOutput, Citation
from contract_review_app.gpt.gpt_dto import GPTDraftResponse


# ------------------------------ public API ----------------------------------

def call_gpt_api(
    clause_type: str,
    prompt: str,
    output: AnalysisOutput,
    model: Optional[str] = "proxy-llm",
) -> GPTDraftResponse:
    """
    Deterministic mock of a GPT drafting endpoint.
    Produces a cleaned clause text using the rule-based analysis context.
    Always returns a non-empty draft_text.
    """
    # 1) Base text: prefer proposed_text from analysis; else original text; else synthetic shell.
    base_text = (getattr(output, "proposed_text", None) or getattr(output, "text", None) or "").strip()
    if not base_text:
        base_text = _fallback_shell(clause_type)

    # 2) Derive a short advisory tail from top recommendations/findings (no external sources).
    advisory_tail = _advisory_tail(output)

    # 3) Compose and apply light guardrails (strip markdown, disclaimers; clamp length).
    raw_draft = _compose(clause_type, base_text, advisory_tail)
    cleaned, actions, _removed = _apply_guardrails(
        text=raw_draft,
        allowed_sources=_extract_allowed_sources(getattr(output, "citations", None) or []),
        max_len=2000,
    )

    if not cleaned:
        cleaned = _fallback_shell(clause_type)  # defensive

    explanation = "Mock draft generated from rule analysis with light guardrails. Actions: " + ", ".join(actions) if actions else "Mock draft."

    return GPTDraftResponse(
        draft_text=cleaned,
        explanation=explanation,
        score=90,
        original_text=getattr(output, "text", "") or "",
        clause_type=clause_type,
        status="ok",
        title=f"Drafted: {clause_type}",
    )


# ------------------------------ internals -----------------------------------

_MARKDOWN_TOKENS = ("```", "# ", "## ", "**", "* ", "> ", "- [", "[SYSTEM]", "[USER]")
_DISCLAIMER_RX = (
    "as an ai",
    "i am an ai",
    "this is not legal advice",
    "as a language model",
    "disclaimer",
)

def _fallback_shell(clause_type: str) -> str:
    return f"Drafted {clause_type.replace('_', ' ').title()} clause."

def _compose(clause_type: str, base_text: str, advisory_tail: str) -> str:
    # Deterministic, no markdown, no headings. Keep it plain.
    parts: List[str] = []
    if base_text:
        parts.append(base_text.strip())
    if advisory_tail:
        parts.append(advisory_tail)
    return "\n".join([p for p in parts if p]).strip()

def _advisory_tail(output: AnalysisOutput) -> str:
    # Build a short, neutral advisory using analysis recommendations or findings.
    try:
        recs = list(getattr(output, "recommendations", None) or [])
        msgs = [str(r).strip() for r in recs if str(r).strip()]
        if not msgs:
            # fallback to finding messages (top-3 by appearance)
            fnds = list(getattr(output, "findings", None) or [])[:3]
            msgs = [str(getattr(f, "message", "")).strip() for f in fnds if str(getattr(f, "message", "")).strip()]
        if msgs:
            return "Consider the following points: " + " ".join(f"- {m}" for m in msgs[:3])
    except Exception:
        pass
    return ""

def _apply_guardrails(
    text: str,
    allowed_sources: List[str],
    max_len: int = 2000,
) -> (str, List[str], List[str]):
    """
    Remove markdown/disclaimers; neutralize unknown source-like chunks; clamp length.
    """
    actions: List[str] = []
    removed: List[str] = []

    if not text:
        return "", actions, removed

    t = text.strip()

    # Strip markdown-like tokens
    for tok in _MARKDOWN_TOKENS:
        if tok in t:
            t = t.replace(tok, "")
            actions.append("strip_markdown")

    # Remove common disclaimers
    low = t.lower()
    for tok in _DISCLAIMER_RX:
        if tok in low:
            lines = [ln for ln in t.splitlines() if tok not in ln.lower()]
            t = "\n".join(lines)
            actions.append("remove_disclaimer")
            low = t.lower()

    # Neutralize bracketed source-like refs if not in allowed list
    if allowed_sources:
        t2, removed_chunks = _neutralize_unknown_sources(t, allowed_sources)
        if removed_chunks:
            t = t2
            removed.extend(removed_chunks)
            actions.append("neutralize_unknown_sources")

    # Clamp length
    if len(t) > max_len:
        t = t[:max_len].rstrip()
        actions.append("clamp_length")

    return t.strip(), actions, removed

def _neutralize_unknown_sources(text: str, allowed: List[str]) -> (str, List[str]):
    """
    Remove simple source-like patterns that are not in the allowed list.
    Heuristic: remove bracketed chunks like (Regulation XYZ) or [Directive 95/46/EC] unless allowed.
    """
    removed: List[str] = []
    out = []
    i = 0
    s = text
    while i < len(s):
        ch = s[i]
        if ch in "([":
            close = ")" if ch == "(" else "]"
            j = s.find(close, i + 1)
            if j != -1:
                chunk = s[i : j + 1]
                chunk_low = chunk.lower()
                if any(tok in chunk_low for tok in ("act", "regulation", "directive", "code", "article", "section")):
                    if not any(src.lower() in chunk_low for src in (allowed or [])):
                        removed.append(chunk)
                        i = j + 1
                        continue
        out.append(ch)
        i += 1
    return "".join(out), removed

def _extract_allowed_sources(citations: List[Citation]) -> List[str]:
    res: List[str] = []
    seen = set()
    for c in citations or []:
        try:
            inst = (c.instrument or "").strip()
            sec = (c.section or "").strip()
            s = f"{inst} {sec}".strip()
            if s and s not in seen:
                seen.add(s)
                res.append(s)
        except Exception:
            continue
    return res
