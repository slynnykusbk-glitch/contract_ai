# contract_review_app/gpt/gpt_orchestrator.py
# ASCII-only. Orchestrates drafting with guardrails and deterministic fallbacks.
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

# Prompt builder (new API with system/user) + legacy fallback
try:
    from contract_review_app.gpt.gpt_prompt_builder import (
        build_gpt_prompt,
        build_prompt,         # legacy shim retained in our builder
        build_prompt_text,    # convenient single-string format
    )
    _HAS_BUILDER = True
except Exception:
    _HAS_BUILDER = False

# GPT proxy (may be absent in local dev)
try:
    from contract_review_app.gpt.gpt_proxy_api import call_gpt_api  # type: ignore
    _HAS_PROXY = True
except Exception:
    _HAS_PROXY = False

# Rule-based fallback synthesizer
try:
    from contract_review_app.engine.pipeline import synthesize_draft  # type: ignore
    _HAS_RULE_FALLBACK = True
except Exception:
    _HAS_RULE_FALLBACK = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_draft(
    analysis: Dict[str, Any],
    mode: str = "friendly",
    use_llm: bool = False,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Decision tree (deterministic):
      1) If analysis.proposed_text exists -> return it (model="rule-template").
      2) If use_llm and proxy available -> build prompt, call LLM, apply guardrails.
      3) Else -> rule-based fallback via pipeline.synthesize_draft (model="rule-based").

    Returns dict with:
      draft_text, mode, model, sources (citations_hint), guardrails{applied[], removed_sources[]},
      explanation (if any), clause_type, status="OK".
    """
    a = dict(analysis or {})
    clause_type = str(a.get("clause_type") or "clause")
    allowed_sources = _extract_allowed_sources(a.get("citations") or [])

    # 1) Prefer rule-provided proposed_text
    proposed = (a.get("proposed_text") or "").strip()
    if proposed:
        cleaned, actions, removed = _apply_guardrails(text=proposed, allowed_sources=allowed_sources, mode=mode, findings=a.get("findings") or [])
        return _draft_out(
            draft_text=cleaned or proposed,
            mode=mode,
            model="rule-template",
            clause_type=clause_type,
            sources=allowed_sources,
            guard_applied=actions,
            removed_sources=removed,
            explanation="Rule template provided.",
        )

    # 2) LLM path (guarded), only if enabled and proxy present
    if use_llm and _HAS_PROXY and _HAS_BUILDER:
        try:
            prompt_text = _prepare_prompt_string(a, mode=mode)
            gpt_resp = call_gpt_api(
                clause_type=clause_type,
                prompt=prompt_text,
                output=a,
                model=model or "proxy-llm",
            )
            draft_text = _get_attr(gpt_resp, "draft_text", default="")
            explanation = _get_attr(gpt_resp, "explanation", default="")
            cleaned, actions, removed = _apply_guardrails(
                text=draft_text,
                allowed_sources=allowed_sources,
                mode=mode,
                findings=a.get("findings") or [],
            )
            if not cleaned:
                # Defensive fallback if model returned empty after guards
                cleaned = _fallback_rule_based(a, mode=mode)
                actions.append("fallback_rule_based_due_to_empty_after_guardrails")
            return _draft_out(
                draft_text=cleaned,
                mode=mode,
                model=model or "proxy-llm",
                clause_type=clause_type,
                sources=allowed_sources,
                guard_applied=actions,
                removed_sources=removed,
                explanation=explanation or "Guarded LLM draft.",
            )
        except Exception as _:
            # Hard fallback to rule-based
            rb = _fallback_rule_based(a, mode=mode)
            return _draft_out(
                draft_text=rb,
                mode=mode,
                model="rule-based",
                clause_type=clause_type,
                sources=allowed_sources,
                guard_applied=["fallback_rule_based_due_to_exception"],
                removed_sources=[],
                explanation="LLM path failed; used rule-based fallback.",
            )

    # 3) Rule-based fallback
    rb = _fallback_rule_based(a, mode=mode)
    return _draft_out(
        draft_text=rb,
        mode=mode,
        model="rule-based" if _HAS_RULE_FALLBACK else "mock",
        clause_type=clause_type,
        sources=allowed_sources,
        guard_applied=["rule_based_fallback"],
        removed_sources=[],
        explanation="LLM disabled or proxy unavailable.",
    )


# Back-compat entry (used by some legacy callers)
def run_gpt_drafting_pipeline(analysis: Union[Dict[str, Any], Any], model: Optional[str] = "gpt-4") -> Dict[str, Any]:
    """
    Legacy wrapper kept for compatibility. Accepts either dict or Pydantic model.
    Uses LLM only if proxy is available.
    """
    # Resolve mode safely
    _mode: Optional[str] = None
    if isinstance(analysis, dict):
        _mode = analysis.get("mode")
    else:
        _mode = getattr(analysis, "mode", None)
        if _mode is None and hasattr(analysis, "model_dump"):
            try:
                _mode = analysis.model_dump().get("mode")  # type: ignore[attr-defined]
            except Exception:
                _mode = None
    # Ensure we pass a dict into run_draft
    if isinstance(analysis, dict):
        a = analysis
    elif hasattr(analysis, "model_dump"):
        try:
            a = analysis.model_dump()  # type: ignore[attr-defined]
        except Exception:
            a = _best_effort_to_dict(analysis)
    else:
        a = _best_effort_to_dict(analysis)
    return run_draft(analysis=a, mode=str(_mode or "friendly"), use_llm=_HAS_PROXY, model=model)


# ---------------------------------------------------------------------------
# Internals: guardrails, prompt prep, utilities
# ---------------------------------------------------------------------------

_DISCLAIMER_RX = (
    "as an ai",
    "i am an ai",
    "this is not legal advice",
    "i cannot",
    "as a language model",
    "disclaimer",
)
_MARKDOWN_TOKENS = ("```", "# ", "## ", "**", "* ", "> ", "- [", "[SYSTEM]", "[USER]")

def _extract_allowed_sources(citations: List[Any]) -> List[str]:
    out: List[str] = []
    seen = set()
    for c in citations or []:
        inst = _get_attr(c, "instrument", "")
        sec = _get_attr(c, "section", "")
        s = f"{inst} {sec}".strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out

def _prepare_prompt_string(analysis: Dict[str, Any], mode: str) -> str:
    """
    Produce a single textual prompt. Uses new builder if present,
    else falls back to legacy builder, else a minimal imperative prompt.
    """
    if _HAS_BUILDER:
        try:
            # Prefer explicit single-string prompt
            return build_prompt_text(analysis=analysis, mode=mode)  # type: ignore
        except Exception:
            try:
                pp = build_gpt_prompt(analysis=analysis, mode=mode)  # type: ignore
                return f"[SYSTEM]\n{pp.system}\n\n[USER]\n{pp.user}"
            except Exception:
                pass
        try:
            legacy = build_prompt(analysis=analysis, mode=mode)  # type: ignore
            # legacy may return dict or string
            if isinstance(legacy, dict):
                return f"[SYSTEM]\n{legacy.get('system','')}\n\n[USER]\n{legacy.get('user','')}"
            return str(legacy)
        except Exception:
            pass
    # Last-resort simple prompt
    base = (analysis.get("proposed_text") or analysis.get("text") or "").strip()
    return f"Rewrite conservatively for a contract clause. Return only clause text.\n---\n{base}\n---"

def _apply_guardrails(
    text: str,
    allowed_sources: List[str],
    mode: str,
    findings: List[Any],
    max_len: int = 2000,
) -> (str, List[str], List[str]):
    """
    Remove meta/markdown/disclaimers; neutralize unknown sources; apply light style normalization per mode.
    Returns (clean_text, actions_applied, removed_sources).
    """
    actions: List[str] = []
    removed_sources: List[str] = []

    if not text:
        return "", actions, removed_sources

    t = text.strip()

    # Strip markdown and obvious meta
    for tok in _MARKDOWN_TOKENS:
        if tok in t:
            t = t.replace(tok, "")
            actions.append("strip_markdown")
            # continue scanning

    low = t.lower()
    for tok in _DISCLAIMER_RX:
        if tok in low:
            # Remove entire lines containing disclaimers
            lines = [ln for ln in t.splitlines() if tok not in ln.lower()]
            t = "\n".join(lines)
            actions.append("remove_disclaimer")
            low = t.lower()

    # Remove/neutralize citations not in allowed list (simple heuristic)
    if allowed_sources:
        # naive patterns: words like "Act", "Regulation", "Directive" and numbers/sections
        suspicious_tokens = (" act", " regulation", " directive", " code", " section ", " article ")
        if any(tok in low for tok in suspicious_tokens):
            # Keep only allowed names by simple inclusion test; drop unknown brackets
            for line in t.splitlines():
                pass  # placeholder for future per-line processing if needed
        # Neutralize bracketed source-like refs if not allowed
        t, removed = _neutralize_unknown_sources(t, allowed_sources)
        if removed:
            actions.append("neutralize_unknown_sources")
            removed_sources.extend(removed)

    # Style normalization by mode (light-touch)
    m = (mode or "friendly").strip().lower()
    if m == "friendly":
        # Prefer softer "should" where easily replaceable without breaking meaning
        t = _soften_obligations(t)
        actions.append("style_friendly")
    elif m == "standard":
        # Ensure "shall" appears at least once for obligations
        if " shall " not in f" {t.lower()} ":
            t = _ensure_shall_once(t)
            actions.append("style_standard_add_shall")
    else:  # strict
        # Ensure explicit timelines/remedies markers if totally absent
        if (" within " not in t.lower()) and (" days" not in t.lower()):
            t = t.rstrip() + " The parties shall perform within agreed timelines."
            actions.append("style_strict_add_timeline")
        if (" remedy" not in t.lower()) and (" remedies" not in t.lower()):
            t = t.rstrip() + " Remedies for breach shall be clearly enforceable."
            actions.append("style_strict_add_remedy")

    # Clamp length
    if len(t) > max_len:
        t = t[:max_len].rstrip()
        actions.append("clamp_length")

    return t.strip(), actions, removed_sources

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
            # find matching ) or ]
            close = ")" if ch == "(" else "]"
            j = s.find(close, i + 1)
            if j != -1:
                chunk = s[i : j + 1]
                chunk_low = chunk.lower()
                # if this chunk mentions a legal-looking term but is not allowed, drop it
                if any(tok in chunk_low for tok in ("act", "regulation", "directive", "code", "article", "section")):
                    if not any(src.lower() in chunk_low for src in (allowed or [])):
                        removed.append(chunk)
                        i = j + 1
                        continue
        out.append(ch)
        i += 1
    return "".join(out), removed

def _soften_obligations(t: str) -> str:
    # Replace "shall" with "should" in non-critical contexts (simple heuristic)
    return t.replace(" shall ", " should ")

def _ensure_shall_once(t: str) -> str:
    # Insert a single "shall" obligation sentence if absent
    return (t.rstrip() + " The parties shall perform their obligations as specified.").strip()

def _fallback_rule_based(analysis: Dict[str, Any], mode: str) -> str:
    if _HAS_RULE_FALLBACK:
        try:
            return synthesize_draft(analysis, mode=mode)  # type: ignore
        except Exception:
            pass
    # Minimal deterministic fallback
    base = (analysis.get("proposed_text") or analysis.get("text") or "").strip()
    if base:
        return f"Suggested edit ({mode}): {base}"
    return f"Drafted clause ({mode})."

def _draft_out(
    draft_text: str,
    mode: str,
    model: str,
    clause_type: str,
    sources: List[str],
    guard_applied: List[str],
    removed_sources: List[str],
    explanation: str,
) -> Dict[str, Any]:
    return {
        "draft_text": draft_text.strip(),
        "mode": (mode or "friendly"),
        "model": model,
        "clause_type": clause_type,
        "status": "OK",
        "sources": list(sources or []),  # citations_hint for API layer
        "guardrails": {
            "applied": guard_applied,
            "removed_sources": removed_sources,
        },
        "explanation": explanation,
    }

def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)

def _best_effort_to_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert unknown analysis-like object to a plain dict without raising.
    """
    try:
        if hasattr(obj, "dict"):
            return obj.dict()  # pydantic v1
    except Exception:
        pass
    try:
        if hasattr(obj, "__dict__"):
            return dict(getattr(obj, "__dict__") or {})
    except Exception:
        pass
    # Last resort: copy a few common attrs if present
    out: Dict[str, Any] = {}
    for f in ("clause_type", "text", "proposed_text", "findings", "citations"):
        try:
            val = getattr(obj, f)
            if val is not None:
                out[f] = val
        except Exception:
            continue
    return out
