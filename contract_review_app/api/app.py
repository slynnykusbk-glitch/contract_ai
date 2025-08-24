# contract_review_app/api/app.py
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# SSOT DTO imports
from contract_review_app.core.schemas import (
    AnalyzeIn,
    DraftIn,
    SuggestIn,
    SuggestOut,
    TextPatch,
    QARecheckIn,
)

# Orchestrator / Engine imports
try:
    from contract_review_app.api.orchestrator import (  # type: ignore
        run_analyze,
        run_qa_recheck,
        run_gpt_draft,
        run_suggest_edits,
    )
except Exception:  # pragma: no cover
    run_analyze = None  # type: ignore
    run_qa_recheck = None  # type: ignore
    run_gpt_draft = None  # type: ignore
    run_suggest_edits = None  # type: ignore

try:
    from contract_review_app.engine import pipeline  # type: ignore
except Exception:  # pragma: no cover
    pipeline = None  # type: ignore

# Optional: rule registry for /health
try:
    from contract_review_app.legal_rules import registry as rules_registry  # type: ignore
except Exception:  # pragma: no cover
    rules_registry = None  # type: ignore

try:
    from contract_review_app.legal_rules import loader as rules_loader  # type: ignore
except Exception:  # pragma: no cover
    rules_loader = None  # type: ignore

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------
SCHEMA_VERSION = os.getenv("CONTRACT_AI_SCHEMA_VERSION", "1.0")
ANALYZE_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_ANALYZE_TIMEOUT_SEC", "25"))
QA_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_QA_TIMEOUT_SEC", "20"))
DRAFT_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_DRAFT_TIMEOUT_SEC", "25"))
MAX_CONCURRENCY = int(os.getenv("CONTRACT_AI_MAX_CONCURRENCY", "4"))
MAX_BODY_BYTES = int(os.getenv("CONTRACT_AI_MAX_BODY_BYTES", str(2_500_000)))
CACHE_SIZE = int(os.getenv("CONTRACT_AI_CACHE_SIZE", "128"))

LEARNING_LOG_PATH = Path(__file__).resolve().parents[2] / "var" / "learning_logs.jsonl"

ALLOWED_ORIGINS = os.getenv(
    "CONTRACT_AI_ALLOWED_ORIGINS",
    "http://127.0.0.1:3000,https://127.0.0.1:3000,http://localhost:3000,https://localhost:3000",
).split(",")
ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
# Ensure local dev and WebView contexts
for _o in (
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
    "null",
):
    if _o not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(_o)

# --------------------------------------------------------------------
# App / Router
# --------------------------------------------------------------------
router = APIRouter()
app = FastAPI(title="Contract Review App API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-cid", "x-cache", "x-schema-version", "x-latency-ms"],
)

# ---- Trace middleware and store ------------------------------------
_TRACE_MAX_CIDS = 200
_TRACE_MAX_EVENTS = 500
_TRACE: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()


def _trace_push(cid: str, event: Dict[str, Any]) -> None:
    if not cid:
        cid = "unknown"
    try:
        slot = _TRACE.get(cid)
        if slot is None:
            if len(_TRACE) >= _TRACE_MAX_CIDS:
                _TRACE.popitem(last=False)
            slot = []
            _TRACE[cid] = slot
        slot.append(event)
        if len(slot) > _TRACE_MAX_EVENTS:
            del slot[: len(slot) - _TRACE_MAX_EVENTS]
    except Exception:
        # never break the request because of tracing
        pass


@app.middleware("http")
async def _trace_mw(request: Request, call_next):
    t0 = _now_ms()
    req_cid = request.headers.get("x-cid", "")
    try:
        response: Response = await call_next(request)
    except Exception as ex:
        _trace_push(req_cid or "unknown", {
            "ts": _now_ms(),
            "method": request.method,
            "path": request.url.path,
            "status": 500,
            "ms": _now_ms() - t0,
            "cache": "",
            "cid": req_cid or "",
        })
        raise ex
    resp_cid = response.headers.get("x-cid", req_cid or "")
    cache = response.headers.get("x-cache", "")
    latency_hdr = response.headers.get("x-latency-ms")
    try:
        ms = int(latency_hdr) if latency_hdr is not None and latency_hdr.isdigit() else (_now_ms() - t0)
    except Exception:
        ms = _now_ms() - t0
    _trace_push(resp_cid or "unknown", {
        "ts": _now_ms(),
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ms": ms,
        "cache": cache,
        "cid": resp_cid,
    })
    return response

# --------------------------------------------------------------------
# Concurrency / Cache
# --------------------------------------------------------------------
_analyze_sem = asyncio.Semaphore(MAX_CONCURRENCY)
_cache_lock = asyncio.Lock()


class _LRUCache(OrderedDict):
    def __init__(self, maxsize: int):
        super().__init__()
        self.maxsize = maxsize

    def get(self, key: str) -> Any:  # type: ignore[override]
        try:
            val = super().__getitem__(key)
            self.move_to_end(key)
            return val
        except KeyError:
            return None

    def put(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self.move_to_end(key)
        if len(self) > self.maxsize:
            self.popitem(last=False)


IDEMPOTENT_CACHE = _LRUCache(CACHE_SIZE)

# --------------------------------------------------------------------
# Schemas (Pydantic) for learning endpoints
# --------------------------------------------------------------------
class LearningUpdateIn(BaseModel):
    force: Optional[bool] = False


# --------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------
def _now_ms() -> int:
    return int(time.time() * 1000)


def _json_dumps_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    except Exception:
        return "{}"


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _idempotency_key(text: str, policy_pack: Optional[Dict[str, Any]]) -> str:
    base = {"text": text, "policy_pack": policy_pack or {}}
    return _sha256_hex(_json_dumps_safe(base))


def _as_dict(model_or_obj: Any) -> Dict[str, Any]:
    if hasattr(model_or_obj, "model_dump"):
        return model_or_obj.model_dump()
    if hasattr(model_or_obj, "dict"):
        return model_or_obj.dict()
    if isinstance(model_or_obj, dict):
        return model_or_obj
    return {"value": model_or_obj}


def _set_std_headers(
    resp: Response,
    *,
    cid: str,
    xcache: str,
    schema: str,
    latency_ms: Optional[int] = None,
) -> None:
    resp.headers["x-cid"] = cid
    resp.headers["x-cache"] = xcache
    resp.headers["x-schema-version"] = schema
    if latency_ms is not None:
        resp.headers["x-latency-ms"] = str(latency_ms)


def _problem_json(status: int, title: str, detail: str, type_: str = "about:blank") -> Dict[str, Any]:
    return {"type": type_, "title": title, "status": status, "detail": detail}


def _problem_response(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=_problem_json(status, title, detail),
    )


async def _read_body_guarded(request: Request) -> bytes:
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    return body


def _coerce_patch_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(by_alias=True)
        if hasattr(obj, "dict"):
            return obj.dict(by_alias=True)  # type: ignore[attr-defined]
    except Exception:
        pass
    out: Dict[str, Any] = {}
    for k in ("range", "span", "replacement", "text"):
        if hasattr(obj, k):
            out[k] = getattr(obj, k)
    return out


def _safe_apply_patches(text: str, changes: List[Any]) -> str:
    if not changes:
        return text or ""

    base = text or ""
    n = len(base)
    items: List[Tuple[int, int, str]] = []

    for raw in changes:
        ch = _coerce_patch_dict(raw) or {}

        src = ch.get("range")
        if not isinstance(src, dict):
            src = ch.get("span") or {}

        start = src.get("start", 0)
        length = src.get("length", None)
        end = src.get("end", None)

        try:
            start = int(start)
        except Exception:
            start = 0

        if length is None and end is not None:
            try:
                end = int(end)
            except Exception:
                end = start
            length = max(0, end - start)
        elif length is None:
            length = 0
        else:
            try:
                length = int(length)
            except Exception:
                length = 0

        if start < 0:
            start = 0
        if length < 0:
            length = 0
        end_pos = start + length
        if end_pos < start:
            end_pos = start
        if start > n:
            start = n
        if end_pos > n:
            end_pos = n

        rep = ch.get("replacement", None)
        if rep is None:
            rep = ch.get("text", "")
        rep = "" if rep is None else str(rep)

        items.append((start, end_pos, rep))

    items.sort(key=lambda t: t[0])
    out: List[str] = []
    cur = 0
    for s, e, rep in items:
        if s < cur or s > n or e > n:
            continue
        out.append(base[cur:s])
        out.append(rep)
        cur = e
    out.append(base[cur:])
    return "".join(out)


def _discover_rules_count() -> int:
    try:
        if rules_loader and hasattr(rules_loader, "rules_count"):
            return int(rules_loader.rules_count())
    except Exception:
        pass
    try:
        if rules_registry and hasattr(rules_registry, "discover_rules"):
            rules = rules_registry.discover_rules()
            return len(rules or [])
    except Exception:
        pass
    return 0


async def _maybe_await(func, *args, **kwargs):
    res = func(*args, **kwargs)
    if asyncio.iscoroutine(res):
        return await res
    return res


def _fallback_suggest_minimal(text: str, clause_id: str, mode: str, top_k: int) -> List[Dict[str, Any]]:
    start = 0
    length = min(len(text), 12) if len(text) > 0 else 0
    proposed = "Please clarify obligations." if mode == "strict" else "Consider adding a clear notice period."
    return [{
        "suggestion_id": f"{clause_id}:1",
        "clause_id": clause_id,
        "clause_type": "unknown",
        "action": "replace" if mode == "strict" else "append",
        "proposed_text": proposed,
        "reason": "rule-fallback",
        "sources": [],
        "range": {"start": int(start), "length": int(length)},
        "hash": _sha256_hex((proposed or "")[:256]),
    }][:max(1, min(top_k or 1, 10))]


def _risk_ord(risk: Optional[str]) -> int:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    return order.get((risk or "").lower(), -1)


def _safe_doc_status(legacy: Dict[str, Any]) -> Optional[str]:
    analysis = legacy.get("analysis") if isinstance(legacy, dict) else None
    if isinstance(analysis, dict):
        return analysis.get("status")
    return None


def _safe_delta_score(before: Dict[str, Any], after: Dict[str, Any]) -> int:
    sb = 0
    sa = 0
    if isinstance(before, dict) and isinstance(before.get("analysis"), dict):
        sb = int(before["analysis"].get("score") or 0)
    if isinstance(after, dict) and isinstance(after.get("analysis"), dict):
        sa = int(after["analysis"].get("score") or 0)
    return sa - sb


def _safe_delta_risk(before: Dict[str, Any], after: Dict[str, Any]) -> int:
    rb = None
    ra = None
    if isinstance(before, dict) and isinstance(before.get("analysis"), dict):
        rb = before["analysis"].get("risk_level")
    if isinstance(after, dict) and isinstance(after.get("analysis"), dict):
        ra = after["analysis"].get("risk_level")
    return _risk_ord(ra) - _risk_ord(rb)


def _top3_residuals(after: Dict[str, Any]) -> List[Dict[str, Any]]:
    analysis = after.get("analysis") if isinstance(after, dict) else None
    findings = (analysis or {}).get("findings") or []
    if not isinstance(findings, list):
        return []
    sev_rank = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    norm: List[Dict[str, Any]] = []
    for f in findings:
        if isinstance(f, dict):
            code = f.get("code")
            msg = f.get("message")
            sev = f.get("severity") or f.get("risk") or f.get("severity_level")
        else:
            code = getattr(f, "code", None)
            msg = getattr(f, "message", None)
            sev = getattr(f, "severity", None) or getattr(f, "risk", None) or getattr(f, "severity_level", None)
        norm.append({"code": code, "message": msg, "severity": sev})
    findings_sorted = sorted(
        norm, key=lambda f: sev_rank.get(str(f.get("severity") or "").lower(), -1), reverse=True
    )
    return findings_sorted[:3]


# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------
@router.get("/health")
async def health(response: Response):
    t0 = _now_ms()
    data = {
        "status": "ok",
        "schema": SCHEMA_VERSION,
        "rules_count": _discover_rules_count(),
        "schema_version": SCHEMA_VERSION,
        "uptime_hint": "process-alive",
    }
    _set_std_headers(response, cid="health", xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return data


@router.get("/api/trace/{cid}")
async def api_trace(cid: str, response: Response):
    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
    return {"status": "ok", "cid": cid, "events": _TRACE.get(cid, [])}


@router.get("/api/trace")
async def api_trace_index(response: Response):
    _set_std_headers(response, cid="trace-index", xcache="miss", schema=SCHEMA_VERSION)
    return {"status": "ok", "cids": list(_TRACE.keys())}


@router.post("/api/analyze")
async def api_analyze(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    try:
        body = await _read_body_guarded(request)
        payload = json.loads(body.decode("utf-8")) if body else {}
    except HTTPException:
        return _problem_response(413, "Payload too large", "Request body exceeds limits")
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    try:
        model = AnalyzeIn(**payload) if isinstance(payload, dict) else AnalyzeIn(text="")
    except Exception as ex:
        return _problem_response(422, "Validation error", str(ex))

    cid = x_cid or _sha256_hex(str(t0) + model.text[:128])
    key = _idempotency_key(model.text or "", getattr(model, "policy_pack", getattr(model, "policy", None)))

    async with _cache_lock:
        cached = IDEMPOTENT_CACHE.get(key)
    if cached is not None:
        _set_std_headers(response, cid=cid, xcache="hit", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return cached

    # Attempt to use orchestrator; if unavailable, return minimal SSOT envelope and cache it.
    local_run_analyze = run_analyze
    if local_run_analyze is None:
        try:
            from contract_review_app.api import orchestrator as _orch  # type: ignore
            local_run_analyze = getattr(_orch, "run_analyze", None)
        except Exception:
            local_run_analyze = None

    if local_run_analyze is None:
        findings = rules_loader.match_text(model.text or "") if rules_loader else []
        envelope = {
            "status": "ok",
            "analysis": {
                "status": "OK",
                "clause_type": "general",
                "risk_level": "medium",
                "score": 0,
                "findings": findings,
            },
            "results": {},
            "clauses": [],
            "document": {"text": model.text or ""},
            "schema_version": SCHEMA_VERSION,
            "meta": {"rules_count": _discover_rules_count()},
        }
        async with _cache_lock:
            IDEMPOTENT_CACHE.put(key, envelope)
        _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return envelope

    try:
        legacy = await asyncio.wait_for(_maybe_await(local_run_analyze, model), timeout=ANALYZE_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        return _problem_response(504, "Timeout", "Analysis timed out")

    envelope = {
        "status": "ok",
        "analysis": legacy.get("analysis") if isinstance(legacy, dict) else None,
        "results": legacy.get("results") if isinstance(legacy, dict) else {},
        "clauses": legacy.get("clauses") if isinstance(legacy, dict) else [],
        "document": legacy.get("document") if isinstance(legacy, dict) else {},
        "schema_version": SCHEMA_VERSION,
        "meta": {"rules_count": _discover_rules_count()},
    }
    if isinstance(legacy, dict):
        analysis = legacy.get("analysis")
        if isinstance(analysis, dict) and "clause_type" not in analysis:
            analysis["clause_type"] = "general"
    async with _cache_lock:
        IDEMPOTENT_CACHE.put(key, envelope)

    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return envelope


@router.post("/api/gpt/draft")
async def api_gpt_draft(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    try:
        body = await _read_body_guarded(request)
        payload = json.loads(body.decode("utf-8")) if body else {}
    except HTTPException:
        return _problem_response(413, "Payload too large", "Request body exceeds limits")
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    model = DraftIn(**payload) if isinstance(payload, dict) else DraftIn()
    cid = x_cid or _sha256_hex(str(t0) + (model.text or "")[:128])

    used_model = getattr(model, "model", None) or "rule-based"
    draft_text: str = ""
    meta_title: Optional[str] = None
    meta_clause_type: Optional[str] = None

    try:
        if run_gpt_draft is not None:
            dr = await asyncio.wait_for(
                _maybe_await(run_gpt_draft, model),
                timeout=DRAFT_TIMEOUT_SEC,
            )
        elif pipeline and hasattr(pipeline, "synthesize_draft"):
            # fallback pipeline path
            doc: Dict[str, Any]
            if model.analysis:
                doc = model.analysis if isinstance(model.analysis, dict) else _as_dict(model.analysis)
            elif run_analyze is not None:
                ana_in = AnalyzeIn(text=model.text or "")
                legacy = await asyncio.wait_for(_maybe_await(run_analyze, ana_in), timeout=ANALYZE_TIMEOUT_SEC)
                doc = legacy.get("document") or {}
            else:
                doc = {}
            dr = await asyncio.wait_for(
                _maybe_await(pipeline.synthesize_draft, doc, mode=(model.mode or "friendly")),
                timeout=DRAFT_TIMEOUT_SEC,
            )
        else:
            dr = {"text": ""}

        if isinstance(dr, str):
            draft_text = dr
        elif isinstance(dr, dict):
            draft_text = str(dr.get("text") or "")
            meta_title = dr.get("title")
            meta_clause_type = dr.get("clause_type")
            used_model = dr.get("model") or used_model
        else:
            draft_text = str(getattr(dr, "text", "") or "")
            meta_title = getattr(dr, "title", None)  # type: ignore[attr-defined]
            meta_clause_type = getattr(dr, "clause_type", None)  # type: ignore[attr-defined]
            used_model = getattr(dr, "model", used_model)  # type: ignore[attr-defined]
    except Exception:
        draft_text = draft_text or "No draft available due to an internal error."

    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return {
        "status": "ok",
        "draft_text": draft_text,
        "citations_hint": [],
        "meta": {
            "model": used_model,
            "title": meta_title,
            "clause_type": meta_clause_type,
        },
    }


@router.post("/api/suggest_edits")
async def api_suggest_edits(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    try:
        body = await _read_body_guarded(request)
        payload = json.loads(body.decode("utf-8")) if body else {}
    except HTTPException:
        return _problem_response(413, "Payload too large", "Request body exceeds limits")
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    if isinstance(payload, dict) and 'top_k' in payload:
        try:
            payload['top_k'] = max(1, min(10, int(payload.get('top_k') or 1)))
        except Exception:
            payload['top_k'] = 1
    try:
        model = SuggestIn(**payload)
    except Exception as ex:
        return _problem_response(422, "Validation error", str(ex))
    cid = x_cid or _sha256_hex(str(t0) + model.text[:128])

    suggestions: List[Dict[str, Any]] = []
    try:
        if run_suggest_edits is not None:
            suggestions = await asyncio.wait_for(
                _maybe_await(
                    run_suggest_edits,
                    model,
                ),
                timeout=DRAFT_TIMEOUT_SEC,
            )
        elif pipeline and hasattr(pipeline, "suggest_edits"):
            suggestions = await asyncio.wait_for(
                _maybe_await(
                    pipeline.suggest_edits,
                    model.text,
                    model.clause_id,
                    getattr(model, "clause_type", None),
                    (model.mode or "friendly"),
                    int(getattr(model, "top_k", 1) or 1),
                ),
                timeout=DRAFT_TIMEOUT_SEC,
            )
            if isinstance(suggestions, dict):
                suggestions = [suggestions]
        else:
            suggestions = []
    except Exception:
        suggestions = []

    if not suggestions:
        suggestions = _fallback_suggest_minimal(
            model.text,
            (model.clause_id or ""),
            model.mode or "friendly",
            int(getattr(model, "top_k", 1) or 1),
        )

    # Robust normalization loop (handles non-dict items safely)
    norm: List[Dict[str, Any]] = []
    for s in suggestions or []:
        # 1) Coerce to dict
        if hasattr(s, "model_dump"):
            try:
                s_dict = s.model_dump()
            except Exception:
                s_dict = {}
        elif isinstance(s, dict):
            s_dict = dict(s)
        elif isinstance(s, str):
            s_dict = {"message": s}
        elif isinstance(s, (list, tuple)):
            try:
                if len(s) == 1:
                    s_dict = {"message": str(s[0])}
                elif len(s) == 2 and not isinstance(s[0], (list, tuple, dict)) and not isinstance(s[1], (list, tuple, dict)):
                    s_dict = {"message": str(s[0]), "proposed_text": str(s[1])}
                else:
                    try:
                        s_dict = dict(s)  # iterable of pairs
                    except Exception:
                        s_dict = {"message": " ".join(map(str, s))}
            except Exception:
                s_dict = {"message": str(s)}
        else:
            s_dict = {"message": str(s)}

        # 2) Normalize range/span to range{start,length}
        start = 0
        length = 0
        r = s_dict.get("range")
        sp = s_dict.get("span")

        if isinstance(r, dict):
            try:
                start = int(r.get("start") or 0)
            except Exception:
                start = 0
            if "length" in r:
                try:
                    length = int(r.get("length") or 0)
                except Exception:
                    length = 0
            else:
                try:
                    end = int(r.get("end") or 0)
                except Exception:
                    end = start
                length = max(0, end - start)
        elif isinstance(sp, dict):
            try:
                start = int(sp.get("start") or 0)
            except Exception:
                start = 0
            if "length" in sp:
                try:
                    length = int(sp.get("length") or 0)
                except Exception:
                    length = 0
            else:
                try:
                    end = int(sp.get("end") or start)
                except Exception:
                    end = start
                length = max(0, end - start)
        elif isinstance(sp, (list, tuple)) and len(sp) == 2:
            try:
                start = int(sp[0] or 0)
            except Exception:
                start = 0
            try:
                end = int(sp[1] or start)
            except Exception:
                end = start
            length = max(0, end - start)

        if start < 0:
            start = 0
        if length < 0:
            length = 0

        s_dict["range"] = {"start": start, "length": length}

        # 3) Ensure message
        msg = s_dict.get("message")
        if not isinstance(msg, str) or msg == "":
            msg = s_dict.get("text") or s_dict.get("proposed_text") or s_dict.get("proposed") or ""
            if not isinstance(msg, str):
                msg = str(msg)
            s_dict["message"] = msg

        # 4) Preserve extra keys and append
        norm.append(s_dict)

    suggestions = norm

    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return {"status": "ok", "suggestions": suggestions}


@router.post("/api/qa-recheck")
async def api_qa_recheck(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    try:
        body = await _read_body_guarded(request)
        payload = json.loads(body.decode("utf-8")) if body else {}
    except HTTPException:
        return _problem_response(413, "Payload too large", "Request body exceeds limits")
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    try:
        model = QARecheckIn(**payload)
    except Exception as ex:
        return _problem_response(422, "Validation error", str(ex))

    cid = x_cid or _sha256_hex(str(t0) + model.text[:128])

    result: Dict[str, Any]
    if run_qa_recheck is not None:
        try:
            result = await asyncio.wait_for(_maybe_await(run_qa_recheck, model), timeout=QA_TIMEOUT_SEC)
            if not isinstance(result, dict):
                result = _as_dict(result)
            if "issues" not in result and "residual_risks" in result:
                result["issues"] = result.get("residual_risks", [])
        except asyncio.TimeoutError:
            return _problem_response(504, "Timeout", "QA Recheck timed out")
        except Exception:
            if run_analyze is not None:
                try:
                    before = await asyncio.wait_for(_maybe_await(run_analyze, AnalyzeIn(text=model.text)), timeout=ANALYZE_TIMEOUT_SEC)
                    patched_text = _safe_apply_patches(model.text, model.applied_changes or [])
                    after = await asyncio.wait_for(_maybe_await(run_analyze, AnalyzeIn(text=patched_text)), timeout=ANALYZE_TIMEOUT_SEC)
                    issues = _top3_residuals(after)
                    result = {
                        "risk_delta": _safe_delta_risk(before, after),
                        "score_delta": _safe_delta_score(before, after),
                        "status_from": _safe_doc_status(before),
                        "status_to": _safe_doc_status(after),
                        "residual_risks": issues,
                        "issues": issues,
                    }
                except Exception as ex2:
                    return _problem_response(500, "QA Recheck failed", f"{ex2}")
            else:
                _ = _safe_apply_patches(model.text, model.applied_changes or [])
                result = {
                    "risk_delta": 0,
                    "score_delta": 0,
                    "status_from": "OK",
                    "status_to": "OK",
                    "residual_risks": [],
                    "issues": [],
                }
    else:
        if run_analyze is not None:
            try:
                before = await asyncio.wait_for(_maybe_await(run_analyze, AnalyzeIn(text=model.text)), timeout=ANALYZE_TIMEOUT_SEC)
                patched_text = _safe_apply_patches(model.text, model.applied_changes or [])
                after = await asyncio.wait_for(_maybe_await(run_analyze, AnalyzeIn(text=patched_text)), timeout=ANALYZE_TIMEOUT_SEC)
                issues = _top3_residuals(after)
                result = {
                    "risk_delta": _safe_delta_risk(before, after),
                    "score_delta": _safe_delta_score(before, after),
                    "status_from": _safe_doc_status(before),
                    "status_to": _safe_doc_status(after),
                    "residual_risks": issues,
                    "issues": issues,
                }
            except Exception as ex2:
                return _problem_response(500, "QA Recheck failed", f"{ex2}")
        else:
            _ = _safe_apply_patches(model.text, model.applied_changes or [])
            result = {
                "risk_delta": 0,
                "score_delta": 0,
                "status_from": "OK",
                "status_to": "OK",
                "residual_risks": [],
                "issues": [],
            }

    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    issues = result.get("issues")
    if issues is None:
        issues = result.get("residual_risks", [])
    payload = {"status": "ok", "issues": issues, **result, "deltas": {
        "score_delta": result.get("score_delta", 0),
        "risk_delta": result.get("risk_delta", 0),
        "status_from": result.get("status_from", "OK"),
        "status_to": result.get("status_to", "OK"),
    }}
    return payload


@router.post("/api/learning/log", status_code=204)
async def api_learning_log(body: Any = Body(...)) -> Response:
    t0 = _now_ms()
    try:
        LEARNING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LEARNING_LOG_PATH.open("a", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False)
            f.write("\n")
    except Exception:
        pass
    resp = Response(status_code=204)
    _set_std_headers(
        resp,
        cid="learning/log",
        xcache="miss",
        schema=SCHEMA_VERSION,
        latency_ms=_now_ms() - t0,
    )
    return resp


@router.post("/api/learning/update")
async def api_learning_update(response: Response, body: LearningUpdateIn):
    t0 = _now_ms()
    _set_std_headers(response, cid="learning/update", xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return {"status": "ok", "updated": True, "force": bool(body.force)}


# Mount router
app.include_router(router)

# --------------------------------------------------------------------
# Static panel mount (/panel) with no-store headers and version endpoint
# --------------------------------------------------------------------
panel_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@panel_app.middleware("http")
async def _panel_no_store_mw(request: Request, call_next):
    resp: Response = await call_next(request)
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@panel_app.get("/version.json")
async def panel_version():
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"schema_version": "1.0", "build": ts}


panel_app.mount("/", StaticFiles(directory="word_addin_dev", html=True), name="panel-static")
app.mount("/panel", panel_app)
