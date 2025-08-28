from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from contract_review_app.rules_v2.i18n import resolve_locale
from contract_review_app.rules_v2.models import ENGINE_VERSION, FindingV2


# --- helpers ---


def _norm_severity(v: str | None) -> str:
    """Map common v1 severities to V2 values."""
    s = (v or "").strip().lower()
    if s in {"critical", "blocker", "high", "severe"}:
        return "High"
    if s in {"medium", "moderate", "warning"}:
        return "Medium"
    if s in {"low", "minor", "info", "informational"}:
        return "Low"
    return "Medium"


def _to_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if i is not None]
    return [str(x)]


def _collapse_citations(cits: Any) -> List[str]:
    """Accepts None | str | dict | list[mixed]; returns list[str]."""
    out: List[str] = []
    if cits is None:
        return out
    src: Iterable[Any] = cits if isinstance(cits, list) else [cits]
    for it in src:
        if it is None:
            continue
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict):
            url = it.get("url") or it.get("link")
            if isinstance(url, str) and url.strip():
                out.append(url.strip())
                continue
            inst = str(it.get("instrument") or "").strip()
            sec = str(it.get("section") or "").strip()
            if inst and sec:
                out.append(f"{inst} §{sec}")
                continue
            title = str(it.get("title") or "").strip()
            if title:
                out.append(title)
        else:
            out.append(str(it))
    return out


# --- core API ---


def adapt_finding_v1_to_v2(v1: Any, *, pack: str, rule_id: str) -> FindingV2:
    """Convert a legacy v1 finding-like object to FindingV2."""
    as_dict: Dict[str, Any] = {}
    if hasattr(v1, "model_dump"):
        as_dict = v1.model_dump()
    elif hasattr(v1, "dict"):
        as_dict = v1.dict()
    elif isinstance(v1, dict):
        as_dict = v1
    else:
        as_dict = {"message": str(v1)}

    code = str(as_dict.get("code") or rule_id or "LEGACY").strip() or "LEGACY"
    msg = str(as_dict.get("message") or "").strip()
    sev = _norm_severity(as_dict.get("severity") or as_dict.get("severity_level"))
    evidence = _to_list(as_dict.get("evidence"))
    citations = _collapse_citations(as_dict.get("citations"))
    flags = _to_list(as_dict.get("tags"))

    now = datetime.now(timezone.utc)

    locale = resolve_locale()
    title = {locale: code, "uk": code}
    message = {locale: msg or code, "uk": msg or code}
    explain = {locale: "", "uk": ""}
    suggestion = {locale: "", "uk": ""}

    f2 = FindingV2(
        id=code,
        pack=pack,
        rule_id=rule_id or code,
        title=title,
        severity=sev,
        category=str(as_dict.get("category") or "General"),
        message=message,
        explain=explain,
        suggestion=suggestion,
        evidence=evidence,
        citation=citations,
        flags=flags,
        meta={},
        version=str(as_dict.get("version") or "2.0.0"),
        created_at=now,
        engine_version=ENGINE_VERSION,
    )
    return f2


def run_legacy_rule(
    rule_fn, context: Dict[str, Any], *, pack: str, rule_id: str
) -> List[FindingV2]:
    """Execute a legacy rule function and adapt its outputs."""
    try:
        res = rule_fn(context)
    except Exception as e:  # pragma: no cover - deterministic path
        return [
            FindingV2(
                id=f"{rule_id}:error",
                pack=pack,
                rule_id=rule_id,
                title={"en": f"{rule_id} failed", "uk": f"{rule_id} failed"},
                severity="High",
                category="System",
                message={"en": str(e), "uk": str(e)},
                explain={
                    "en": "Legacy rule execution failed",
                    "uk": "Legacy rule execution failed",
                },
                suggestion={
                    "en": "Check rule compatibility/migration",
                    "uk": "Check rule compatibility/migration",
                },
                evidence=[],
                citation=[],
                flags=["legacy", "error"],
                meta={},
                version="2.0.0",
                created_at=datetime.now(timezone.utc),
                engine_version=ENGINE_VERSION,
            )
        ]

    if res is None:
        items: List[Any] = []
    elif isinstance(res, list):
        items = res
    else:
        items = [res]

    out: List[FindingV2] = []
    for it in items:
        out.append(adapt_finding_v1_to_v2(it, pack=pack, rule_id=rule_id))
    return out
