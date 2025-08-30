from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

# This module works entirely in-memory; no data is persisted to disk or external storage.

logger = logging.getLogger(__name__)

_ALLOWED_DOMAINS = {
    "www.legislation.gov.uk",
    "www.courtservice.gov.uk",
    "ico.org.uk",
    "www.gov.uk",
    "eur-lex.europa.eu",
    "www.legislationline.org",
}


@dataclass(frozen=True)
class ResolvedCitation:
    id: str
    system: str
    instrument: str
    section: str
    url: Optional[str] = None
    source: Optional[str] = None
    title: Optional[str] = None


def _norm_str(x: Any) -> str:
    return (str(x or "")).strip()


def _domain_ok(u: str) -> bool:
    try:
        parsed = urlparse(u)
        netloc = parsed.netloc.lower()
        scheme = parsed.scheme.lower()
    except Exception:
        return False
    # Only allow HTTPS requests to whitelisted domains
    return bool(netloc) and scheme == "https" and (netloc in _ALLOWED_DOMAINS)


def normalize_citations(items: Any) -> List[ResolvedCitation]:
    """
    Accepts None|str|dict|list[mixed]; returns unique list of ResolvedCitation with whitelist filtering.
    Dedup key: (system,instrument,section,url or '').

    Evidence text is never logged to avoid PII leakage.
    """
    try:
        if items is None:
            return []
        src: Iterable[Any] = items if isinstance(items, list) else [items]
        out: List[ResolvedCitation] = []
        seen: set[tuple[str, str, str, str]] = set()
        idx = 1
        for it in src:
            sys = inst = sec = url = title = src_name = ""
            if isinstance(it, str):
                inst = _norm_str(it)
            elif isinstance(it, dict):
                sys = _norm_str(it.get("system"))
                inst = _norm_str(it.get("instrument"))
                sec = _norm_str(it.get("section"))
                url = _norm_str(it.get("url") or it.get("link"))
                title = _norm_str(it.get("title"))
                src_name = _norm_str(it.get("source"))
            else:
                inst = _norm_str(it)
            # URL whitelist (if present)
            if url and not _domain_ok(url):
                url = ""
            key = (sys or "UK", inst, sec, url)
            if key in seen:
                continue
            seen.add(key)
            cid = f"c{idx}"
            idx += 1
            out.append(
                ResolvedCitation(
                    id=cid,
                    system=sys or "UK",
                    instrument=inst or "unknown",
                    section=sec,
                    url=url or None,
                    source=src_name or None,
                    title=title or None,
                )
            )
        return out
    except Exception as exc:
        logger.warning("normalize_citations failed: %s", exc)
        return []


def make_grounding_pack(
    question: str, context_text: str, citations: Any
) -> Dict[str, Any]:
    """
    Build a deterministic grounding package for prompt_builder.
    Evidence items are derived from normalized citations.

    The evidence text is not logged to avoid leaking contract details.
    """
    try:
        norm = normalize_citations(citations)
        evidence: List[Dict[str, Any]] = []
        for rc in norm:
            label = f"{rc.instrument} §{rc.section}".strip()
            src = rc.url or rc.source or rc.system
            evidence.append({"id": rc.id, "text": label, "source": src})
        return {
            "question": question or "",
            "context": context_text or "",
            "citations": [c.__dict__ for c in norm],
            "evidence": evidence,
        }
    except Exception as exc:
        logger.warning("make_grounding_pack failed: %s", exc)
        return {
            "question": question or "",
            "context": context_text or "",
            "citations": [],
            "evidence": [],
        }
