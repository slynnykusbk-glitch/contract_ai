from __future__ import annotations

import copy
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping

from contract_review_app.legal_rules import loader

# ---------------------------------------------------------------------------
# L0 trace hook plumbing
# ---------------------------------------------------------------------------

log = logging.getLogger(__name__)


_L0_HOOK_CTX: ContextVar[Dict[str, Any] | None] = ContextVar(
    "_L0_HOOK_CTX", default=None
)
_L0_HOOK_GLOBAL: Dict[str, Any] | None = None
_L0_TRACE_PENDING: Dict[str, Dict[str, Dict[str, Any]]] = {}
_TRACE_PATCHED = False


def _current_l0_state() -> Dict[str, Any] | None:
    ctx_state = _L0_HOOK_CTX.get()
    if ctx_state is not None:
        return ctx_state
    return _L0_HOOK_GLOBAL


def _configure_l0_hook(state: Mapping[str, Any] | None) -> None:
    """Install a global fallback *state* for the L0 hook."""

    global _L0_HOOK_GLOBAL
    _L0_HOOK_GLOBAL = dict(state) if state else None


@contextmanager
def _l0_hook_context(state: Mapping[str, Any] | None) -> Iterable[None]:
    """Context manager to temporarily override the L0 hook state."""

    token = _L0_HOOK_CTX.set(dict(state) if state else None)
    try:
        yield
    finally:
        _L0_HOOK_CTX.reset(token)


def _resolve_cid(state: Mapping[str, Any]) -> str | None:
    cid = state.get("cid")
    if cid:
        return str(cid)
    provider = state.get("cid_provider")
    if callable(provider):
        try:
            return provider() or None
        except Exception:  # pragma: no cover - defensive
            log.exception("L0 hook cid provider raised")
            return None
    return None


def _default_trace_push(cid: str, event: Dict[str, Any]) -> None:
    try:
        from contract_review_app.api import app as api_app  # type: ignore
    except Exception:
        return

    push = getattr(api_app, "_trace_push", None)
    if callable(push):
        try:
            push(cid, event)
        except Exception:  # pragma: no cover - logging only
            log.exception("Failed to push L0 event to trace store")


def _ensure_trace_patch() -> None:
    global _TRACE_PATCHED
    if _TRACE_PATCHED:
        return
    try:
        from contract_review_app.api import app as api_app  # type: ignore
    except Exception:
        return

    trace_store = getattr(api_app, "TRACE", None)
    if trace_store is None:
        return

    original_put = trace_store.put

    def wrapped_put(cid: str, item: Dict[str, Any]) -> None:
        original_put(cid, item)
        _flush_pending_trace(trace_store, cid)

    try:
        trace_store.put = wrapped_put  # type: ignore[assignment]
    except Exception:  # pragma: no cover - defensive
        return
    _TRACE_PATCHED = True


def _record_metrics(state: Mapping[str, Any], payload: Dict[str, Any]) -> None:
    collector = state.get("metrics")
    if collector is None:
        return
    try:
        if callable(collector):
            collector(payload)
        elif hasattr(collector, "append"):
            collector.append(payload)  # type: ignore[attr-defined]
        elif isinstance(collector, MutableMapping):
            bucket = collector.setdefault("segments", [])
            if isinstance(bucket, list):
                bucket.append(payload)
    except Exception:  # pragma: no cover - metrics never break flow
        log.exception("L0 metrics collector failed")


def _queue_trace_event(cid: str, segment: Dict[str, Any], labels: Any) -> None:
    _ensure_trace_patch()

    info = {
        "segment_id": segment.get("id"),
        "labels": labels,
        "heading": segment.get("heading"),
        "text": segment.get("text"),
    }
    pending = _L0_TRACE_PENDING.setdefault(cid, {})
    pending[str(segment.get("id"))] = info


def _flush_pending_trace(trace_store: Any, cid: str) -> None:
    if not cid:
        return
    pending = _L0_TRACE_PENDING.pop(cid, None)
    if not pending:
        return

    try:
        snapshot = trace_store.get(cid)
    except Exception:  # pragma: no cover - defensive
        return
    if not snapshot:
        return

    body = snapshot.get("body")
    if not isinstance(body, dict):
        return

    segments_container = body.setdefault("_trace", {}).setdefault("segments", {})
    list_container = body.setdefault("_trace_segments", [])
    direct_map = body.setdefault("_l0_segments", {})

    for seg_id, payload in pending.items():
        entry = {
            "segment_id": payload.get("segment_id"),
            "labels": payload.get("labels"),
        }
        segments_container[seg_id] = entry
        list_container.append(entry)
        direct_map[seg_id] = payload.get("labels")


def _resolve_labels(state: Mapping[str, Any], segment: Dict[str, Any]) -> Any:
    resolver = state.get("resolver")
    if callable(resolver):
        try:
            return resolver(segment)
        except Exception:  # pragma: no cover - resolver errors are logged
            log.exception("L0 resolver callable failed")
            return None

    labels_source = state.get("labels") or state.get("cache")
    if callable(labels_source):
        try:
            return labels_source(segment)
        except Exception:  # pragma: no cover - resolver errors are logged
            log.exception("L0 labels callable failed")
            return None

    if isinstance(labels_source, Mapping):
        seg_id = segment.get("id")
        return labels_source.get(seg_id) or labels_source.get(str(seg_id))
    if isinstance(labels_source, list):
        seg_id = segment.get("id")
        if isinstance(seg_id, int) and 0 <= seg_id - 1 < len(labels_source):
            return labels_source[seg_id - 1]
    if isinstance(labels_source, MutableMapping):
        seg_id = segment.get("id")
        return labels_source.get(seg_id)
    return None


def _attach_l0_labels_if_present(segment: Dict[str, Any]) -> None:
    state = _current_l0_state()
    env_enabled = os.getenv("FEATURE_L0_TRACE", "").lower() in {"1", "true", "yes"}
    if not state and not env_enabled:
        return

    enabled = bool((state or {}).get("enabled", False) or env_enabled)
    if not enabled:
        return

    labels = _resolve_labels(state or {}, segment) if state else None
    if labels in (None, [], {}):
        return

    # store a copy to avoid accidental downstream mutation
    segment["l0_labels"] = copy.deepcopy(labels)

    payload = {"segment_id": segment.get("id"), "labels": labels}
    if state:
        _record_metrics(state, payload)

    cid = _resolve_cid(state or {}) if state else None
    if cid:
        _queue_trace_event(cid, segment, copy.deepcopy(labels))
        trace_cb = state.get("trace_callback") if state else None
        if callable(trace_cb):
            try:
                trace_cb(cid, {"l0_labels": payload})
            except Exception:  # pragma: no cover - logging only
                log.exception("Custom L0 trace callback failed")
        else:
            _default_trace_push(cid, {"l0_labels": payload})


# Mapping of clause types to regex patterns used for detection.
# Patterns are searched in both heading and text of a segment.
_CLAUSE_PATTERNS: Dict[str, List[re.Pattern[str]]] = {
    "governing_law": [
        re.compile(r"governing\s+law", re.I),
        re.compile(r"choice\s+of\s+law", re.I),
        re.compile(r"governed\s+by\s+the\s+laws?", re.I),
    ],
    "confidentiality": [
        re.compile(r"confidential", re.I),
        re.compile(r"non[-\s]?disclosure", re.I),
    ],
    "limitation_of_liability": [
        re.compile(r"limitation\s+of\s+liabilit", re.I),
        re.compile(r"limit[^\n]{0,40}liabilit", re.I),
        re.compile(r"liabilit", re.I),
    ],
    "intellectual_property": [
        re.compile(r"intellectual\s+property", re.I),
        re.compile(r"\bipr\b", re.I),
    ],
    "data_protection": [
        re.compile(r"data\s+protection", re.I),
        re.compile(r"\bgdpr\b", re.I),
        re.compile(r"personal\s+data", re.I),
    ],
    "dispute_resolution": [
        re.compile(r"dispute\s+resolution", re.I),
        re.compile(r"jurisdiction", re.I),
        re.compile(r"arbitration", re.I),
        re.compile(r"courts?", re.I),
    ],
    "definitions": [
        re.compile(r"definitions", re.I),
        re.compile(r"interpretation", re.I),
    ],
    "pricing": [
        re.compile(r"pricing|rates?", re.I),
        re.compile(r"charge[s]?", re.I),
    ],
    "invoice": [
        re.compile(r"invoice", re.I),
    ],
    "payment": [
        re.compile(r"payment", re.I),
        re.compile(r"pay[-\s]?ment", re.I),
    ],
    "parties": [
        re.compile(r"parties", re.I),
    ],
    "quality_management": [
        re.compile(r"quality\s+management", re.I),
        re.compile(r"quality\s+plan", re.I),
        re.compile(r"ISO\s*9001", re.I),
    ],
    "inspections_tests": [
        re.compile(r"inspection", re.I),
        re.compile(r"test\s+plan", re.I),
        re.compile(r"LOLER", re.I),
        re.compile(r"PUWER", re.I),
    ],
}


def _detect_clause(text: str) -> str | None:
    """Return clause_type inferred from *text* or ``None``."""
    for ctype, pats in _CLAUSE_PATTERNS.items():
        for pat in pats:
            if pat.search(text):
                return ctype
    return None


def classify_segments(segments: List[Dict]) -> None:
    """Enrich *segments* in-place with ``clause_type`` and rule findings.

    For each segment a ``clause_type`` is inferred from its heading/text.  If a
    type is determined, deterministic YAML rules are executed against the
    segment's text and any matching findings are stored under ``findings``.
    """

    for seg in segments:
        _attach_l0_labels_if_present(seg)
        heading = seg.get("heading") or ""
        text = seg.get("text") or ""
        combined = f"{heading} {text}".lower()

        clause_type = _detect_clause(combined)
        seg["clause_type"] = clause_type

        if not clause_type:
            continue

        # Execute deterministic rules and retain only those matching this clause
        # type.  The loader returns findings already structured with ``scope``
        # and ``occurrences`` fields, which we keep untouched.
        findings = loader.match_text(text)
        seg["findings"] = [f for f in findings if f.get("clause_type") == clause_type]
