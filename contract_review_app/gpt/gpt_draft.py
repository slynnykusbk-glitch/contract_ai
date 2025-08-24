# contract_review_app/gpt/gpt_draft.py
# ASCII-only. Guarded drafting with deterministic fallbacks for Innovator LegalTech MAX.
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

# Prompt builder (new API with system/user) + legacy shim
try:
    from contract_review_app.gpt.gpt_prompt_builder import (
        build_gpt_prompt,
        build_prompt_text,
        build_prompt,  # legacy
    )
    _HAS_BUILDER = True
except Exception:
    _HAS_BUILDER = False

# Proxy to LLM (mock or real proxy)
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

# Learning adaptor (optional, local-only)
try:
    from contract_review_app.learning import adaptor as _learn  # type: ignore
    _HAS_LEARNING = True
except Exception:
    _learn = None
    _HAS_LEARNING = False


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def generate_guarded_draft(
    analysis: Union[Dict[str, Any], Any],
    mode: str = "friendly",
    use_llm: bool = False,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Decision tree:
      1) If analysis.proposed_text exists -> return it (model="rule-template") after guardrails.
      2) Else if use_llm and proxy available -> build prompt, call proxy, apply guardrails.
      3) Else -> rule-based fallback via pipeline.synthesize_draft (model="rule-based").

    Returns dict with keys:
      - draft_text: str
      - mode: str
      - model: str ("rule-template" | provided model | "rule-based" | "mock")
      - clause_type: str
      - sources: list[str] (citations_hint)
      - guardrails: {applied: list[str], removed_sources: list[str], risk_alignment: list[str]}
      - explanation: str
      - status: "OK"
      - learning: {"enabled": bool, "template_id"?: str, "final_score"?: float, "segment_key"?: str}
    """
    a = _norm_analysis(analysis)
    clause_type = a.get("clause_type") or "clause"
    allowed_sources = _extract_allowed_sources(a.get("citations") or [])
    high_or_critical = _has_high_or_critical(a.get("findings") or [])

    # Learning hint (non-destructive, affects style preference only)
    lh = _learning_hint(a, mode)

    # 1) Rule-provided proposed_text has highest priority
    proposed = (a.get("proposed_text") or "").strip()
    if proposed:
        cleaned, actions, removed = _apply_guardrails(
            text=proposed,
            allowed_sources=allowed_sources,
            mode=mode,
            findings=a.get("findings") or [],
        )
        aligned, align_actions = _align_with_findings(cleaned or proposed, clause_type, high_or_critical, mode)
        return _draft_out(
            draft_text=aligned,
            mode=mode,
            model="rule-template",
            clause_type=clause_type,
            sources=allowed_sources,
            guard_applied=actions,
            removed_sources=removed,
            risk_alignment=align_actions,
            explanation="Rule template provided.",
            learning=lh,
        )

    # 2) LLM path (guarded)
    if use_llm and _HAS_PROXY and _HAS_BUILDER:
        try:
            prompt = _prepare_prompt(a, mode=mode)
            if lh.get("enabled"):
                # Mild, non-destructive style hint for LLM; guardrails still prevent risk downgrade or fake sources
                prompt = (prompt + "\n\nStyle preference: "
                          f"{lh.get('template_id')} (final_score={lh.get('final_score')}).")
            # Pass the original analysis object to proxy to let it leverage context
            gpt_resp = call_gpt_api(
                clause_type=clause_type,
                prompt=prompt,
                output=a,  # type: ignore[arg-type]
                model=model or "proxy-llm",
            )
            draft_text = _get_attr(gpt_resp, "draft_text", "")
            explanation = _get_attr(gpt_resp, "explanation", "")
            cleaned, actions, removed = _apply_guardrails(
                text=draft_text,
                allowed_sources=allowed_sources,
                mode=mode,
                findings=a.get("findings") or [],
            )
            if not cleaned:
                cleaned = _fallback_rule_based(a, mode)
                actions.append("fallback_rule_based_due_to_empty_after_guardrails")
            aligned, align_actions = _align_with_findings(cleaned, clause_type, high_or_critical, mode)
            return _draft_out(
                draft_text=aligned,
                mode=mode,
                model=model or "proxy-llm",
                clause_type=clause_type,
                sources=allowed_sources,
                guard_applied=actions,
                removed_sources=removed,
                risk_alignment=align_actions,
                explanation=explanation or "Guarded LLM draft.",
                learning=lh,
            )
        except Exception:
            # Hard fallback to rule-based
            rb = _fallback_rule_based(a, mode)
            return _draft_out(
                draft_text=rb,
                mode=mode,
                model="rule-based",
                clause_type=clause_type,
                sources=allowed_sources,
                guard_applied=["fallback_rule_based_due_to_exception"],
                removed_sources=[],
                risk_alignment=[],
                explanation="LLM path failed; used rule-based fallback.",
                learning=lh,
            )

    # 3) Rule-based fallback
    rb = _fallback_rule_based(a, mode)
    return _draft_out(
        draft_text=rb,
        mode=mode,
        model="rule-based" if _HAS_RULE_FALLBACK else "mock",
        clause_type=clause_type,
        sources=allowed_sources,
        guard_applied=["rule_based_fallback"],
        removed_sources=[],
        risk_alignment=[],
        explanation="LLM disabled or proxy unavailable.",
        learning=lh,
    )


# -----------------------------------------------------------------------------
# Internals: normalization, learning, prompts, guardrails, alignment
# -----------------------------------------------------------------------------

def _norm_analysis(analysis: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    if isinstance(analysis, dict):
        return dict(analysis)
    out: Dict[str, Any] = {}
    for k in (
        "clause_type",
        "status",
        "risk",
        "risk_level",
        "severity",
        "text",
        "proposed_text",
        "findings",
        "citations",
    ):
        out[k] = getattr(analysis, k, None)
    return out

def _has_high_or_critical(findings: List[Any]) -> bool:
    for f in findings or []:
        sev = _get_attr(f, "severity", None) or _get_attr(f, "severity_level", None)
        if isinstance(sev, str) and sev.lower() in ("high", "major", "critical"):
            return True
    return False

def _extract_allowed_sources(citations: List[Any]) -> List[str]:
    res: List[str] = []
    seen = set()
    for c in citations or []:
        inst = _get_attr(c, "instrument", "").strip()
        sec = _get_attr(c, "section", "").strip()
        s = f"{inst} {sec}".strip()
        if s and s not in seen:
            seen.add(s)
            res.append(s)
    return res

def _segment_key_for_learning(clause_type: str, mode: str,
                              jurisdiction: str = "UK",
                              contract_type: str = "generic",
                              user_role: str = "neutral") -> str:
    # Deterministic ASCII-only segment key
    return (f"(clause_type={clause_type}|mode={mode}|jurisdiction={jurisdiction}"
            f"|contract_type={contract_type}|role={user_role})")

def _learning_hint(analysis: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """
    Non-destructive learning hint:
    - queries adaptor.rank_templates(...) by segment_key
    - computes final_score = 0.7*base + 0.3*learned with clamp |final-base|<=0.25
    - returns {"enabled", "template_id", "base_score", "learned_score", "final_score", "segment_key"}
    """
    if not _HAS_LEARNING or not getattr(_learn, "rank_templates", None):
        return {"enabled": False}
    clause_type = str(analysis.get("clause_type") or "clause")
    m = (mode or "standard").strip().lower()
    if m not in ("friendly", "standard", "strict"):
        m = "standard"

    # Baseline template IDs/scores must be stable across releases
    presets = {
        "friendly": ("GEN_FRIENDLY_01", 0.60),
        "standard": ("GEN_STANDARD_01", 0.70),
        "strict":   ("GEN_STRICT_01",   0.80),
    }
    tpl_id, base = presets[m]
    seg = _segment_key_for_learning(clause_type, m)

    try:
        ranked = _learn.rank_templates(clause_type=clause_type, context={"segment_key": seg}) or []
        learned_map = {str(it.get("template_id") or ""): float(it.get("score") or 0.0) for it in ranked if isinstance(it, dict)}
        ls = float(learned_map.get(tpl_id, base))
        final = 0.7 * base + 0.3 * ls
        if final > base + 0.25:
            final = base + 0.25
        if final < base - 0.25:
            final = base - 0.25
        return {
            "enabled": True,
            "template_id": tpl_id,
            "base_score": round(base, 4),
            "learned_score": round(ls, 4),
            "final_score": round(final, 4),
            "segment_key": seg,
        }
    except Exception:
        return {"enabled": False}

def _prepare_prompt(analysis: Dict[str, Any], mode: str) -> str:
    # Prefer single-string prompt if available
    if _HAS_BUILDER:
        try:
            return build_prompt_text(analysis=analysis, mode=mode)  # type: ignore
        except Exception:
            try:
                pp = build_gpt_prompt(analysis=analysis, mode=mode)  # type: ignore
                return f"[SYSTEM]\n{pp.system}\n\n[USER]\n{pp.user}"
            except Exception:
                pass
        try:
            legacy = build_prompt(analysis=analysis, mode=mode)  # type: ignore
            if isinstance(legacy, dict):
                return f"[SYSTEM]\n{legacy.get('system','')}\n\n[USER]\n{legacy.get('user','')}"
            return str(legacy)
        except Exception:
            pass
    base = (analysis.get("proposed_text") or analysis.get("text") or "").strip()
    return f"Rewrite conservatively for a contract clause. Return only clause text.\n---\n{base}\n---"

_MARKDOWN_TOKENS = ("```", "# ", "## ", "**", "* ", "> ", "- [", "[SYSTEM]", "[USER]")
_DISCLAIMER_RX = (
    "as an ai",
    "i am an ai",
    "this is not legal advice",
    "as a language model",
    "disclaimer",
)

def _apply_guardrails(
    text: str,
    allowed_sources: List[str],
    mode: str,
    findings: List[Any],
    max_len: int = 2000,
) -> Tuple[str, List[str], List[str]]:
    """
    Basic guards: normalize newlines, strip markdown, remove disclaimers,
    neutralize unknown sources, style normalization, clamp and compact.
    Returns (clean_text, actions_applied, removed_sources).
    """
    actions: List[str] = []
    removed: List[str] = []

    if not text:
        return "", actions, removed

    t = text.strip()
    # Normalize newlines deterministically
    t = t.replace("\r\n", "\n").replace("\r", "\n")

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

    # Light style normalization per mode
    m = (mode or "friendly").strip().lower()
    if m == "friendly":
        t = _soften_obligations(t)
        actions.append("style_friendly")
    elif m == "standard":
        if " shall " not in f" {t.lower()} ":
            t = _ensure_shall_once(t)
            actions.append("style_standard_add_shall")
    else:  # strict
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

    # Collapse multiple blank lines (better for Word)
    lines = [ln.rstrip() for ln in t.split("\n")]
    compact: List[str] = []
    empty = 0
    for ln in lines:
        if ln == "":
            empty += 1
            if empty > 1:
                continue
        else:
            empty = 0
        compact.append(ln)
    t = "\n".join(compact)

    return t.strip(), actions, removed

def _align_with_findings(
    text: str,
    clause_type: str,
    high_or_critical: bool,
    mode: str,
) -> Tuple[str, List[str]]:
    """
    Ensure the draft does not undercut high/critical findings.
    Heuristics: enforce at least one hard obligation ('shall'), ensure timeline/remedy markers,
    add a generic compliance line for notice/cure/limits without hard-coding clause specifics.
    """
    actions: List[str] = []
    t = text or ""

    if not high_or_critical:
        return t, actions

    low = t.lower()
    # 1) Ensure "shall" occurs at least once
    if " shall " not in f" {low} ":
        t = _ensure_shall_once(t)
        actions.append("align_add_shall")

    # 2) Ensure a timeline marker
    if (" within " not in low) and (" days" not in low) and (" no later than " not in low):
        t = t.rstrip() + " The parties shall meet applicable timelines where specified."
        actions.append("align_add_timeline_hint")

    # 3) Generic compliance line (notice/cure/limits)
    if ("notice" not in low) and ("cure" not in low) and ("limit" not in low):
        t = t.rstrip() + " The parties shall comply with any applicable notice, cure and limitation requirements."
        actions.append("align_add_notice_cure_limits_hint")

    return t, actions

def _neutralize_unknown_sources(text: str, allowed: List[str]) -> Tuple[str, List[str]]:
    """
    Remove simple source-like patterns that are not in the allowed list.
    Heuristic: strip bracketed chunks mentioning Act/Regulation/Directive/Article/Section unless they match allowed.
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

def _soften_obligations(t: str) -> str:
    # Replace " shall " with " should " where safe (very light-touch)
    return t.replace(" shall ", " should ")

def _ensure_shall_once(t: str) -> str:
    return (t.rstrip() + " The parties shall perform their obligations as specified.").strip()

def _fallback_rule_based(analysis: Dict[str, Any], mode: str) -> str:
    if _HAS_RULE_FALLBACK:
        try:
            return synthesize_draft(analysis, mode=mode)  # type: ignore
        except Exception:
            pass
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
    risk_alignment: List[str],
    explanation: str,
    learning: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = {
        "draft_text": (draft_text or "").strip(),
        "mode": (mode or "friendly"),
        "model": model,
        "clause_type": clause_type,
        "status": "OK",
        "sources": list(sources or []),
        "guardrails": {
            "applied": list(guard_applied or []),
            "removed_sources": list(removed_sources or []),
            "risk_alignment": list(risk_alignment or []),
        },
        "explanation": explanation,
    }
    out["learning"] = (learning if isinstance(learning, dict) and learning.get("enabled") else {"enabled": False})
    return out

def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


__all__ = ["generate_guarded_draft"]
