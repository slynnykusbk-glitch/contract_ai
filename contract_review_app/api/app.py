# contract_review_app/api/app.py
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contract_review_app.api.calloff_validator import validate_calloff
from contract_review_app.gpt.service import (
    LLMService,
    ProviderAuthError,
    ProviderTimeoutError,
    ProviderConfigError,
)
from contract_review_app.gpt.config import load_llm_config

# SSOT DTO imports
from contract_review_app.core.schemas import AnalyzeIn

# Snapshot extraction heuristics
# Snapshot extraction heuristics
from contract_review_app.analysis.extract_summary import extract_document_snapshot

# Orchestrator / Engine imports
try:
    from contract_review_app.api.orchestrator import (  # type: ignore
        run_qa_recheck,
        run_gpt_draft,
        run_suggest_edits,
    )
except Exception:  # pragma: no cover
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
SCHEMA_VERSION = os.getenv("CONTRACT_AI_SCHEMA_VERSION", "1.3")
ANALYZE_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_ANALYZE_TIMEOUT_SEC", "25"))
QA_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_QA_TIMEOUT_SEC", "20"))
DRAFT_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_DRAFT_TIMEOUT_SEC", "25"))
MAX_CONCURRENCY = int(os.getenv("CONTRACT_AI_MAX_CONCURRENCY", "4"))
MAX_BODY_BYTES = int(os.getenv("CONTRACT_AI_MAX_BODY_BYTES", str(2_500_000)))
CACHE_SIZE = int(os.getenv("CONTRACT_AI_CACHE_SIZE", "128"))

# weighted risk scoring (configurable)
RISK_WEIGHTS = {
    "critical": int(os.getenv("CONTRACT_AI_WEIGHT_CRITICAL", "10")),
    "high": int(os.getenv("CONTRACT_AI_WEIGHT_HIGH", "7")),
    "medium": int(os.getenv("CONTRACT_AI_WEIGHT_MEDIUM", "4")),
    "low": int(os.getenv("CONTRACT_AI_WEIGHT_LOW", "1")),
}

REQUIRED_EXHIBITS = {
    e.strip().upper()
    for e in os.getenv("CONTRACT_AI_REQUIRED_EXHIBITS", "M").split(",")
    if e.strip()
}
_PLACEHOLDER_RE = re.compile(r"(\[[^\]]+\]|\bTBD\b|\bTO BE DETERMINED\b)", re.IGNORECASE)
_EXHIBIT_RE = re.compile(r"exhibit\s+([A-Z])", re.IGNORECASE)

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

_LLM_KEY_ENV_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_API_KEY")


def _has_llm_keys() -> bool:
    return any(os.getenv(k) for k in _LLM_KEY_ENV_VARS)

LLM_CONFIG = load_llm_config()
LLM_SERVICE = LLMService(LLM_CONFIG)


def _analyze_document(text: str) -> dict:
    """Hook for tests to analyze document text.

    Default implementation uses the rule engine if available and returns a
    minimal dictionary structure so that tests can monkeypatch this function
    without importing heavy dependencies.
    """
    try:
        from contract_review_app.legal_rules.legal_rules import analyze as rules_analyze
        from contract_review_app.core.schemas import AnalysisInput

        out = rules_analyze(AnalysisInput(text=text, clause_type=None))
        if hasattr(out, "model_dump"):
            out = out.model_dump()
        if isinstance(out, dict):
            return {"status": out.get("status", "OK"), "findings": out.get("findings", [])}
    except Exception:
        pass
    return {"status": "OK", "findings": []}

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
    expose_headers=[
        "x-cid",
        "x-cache",
        "x-schema-version",
        "x-latency-ms",
        "x-provider",
        "x-model",
        "x-llm-mode",
        "x-usage-total",
    ],
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


def _set_schema_headers(response: Response) -> None:
    try:
        response.headers["x-schema-version"] = SCHEMA_VERSION
    except Exception:
        pass


def _set_std_headers(
    resp: Response,
    *,
    cid: str,
    xcache: str,
    schema: str,
    latency_ms: Optional[int] = None,
) -> None:
    _set_schema_headers(resp)
    resp.headers["x-cid"] = cid
    resp.headers["x-cache"] = xcache
    if latency_ms is not None:
        resp.headers["x-latency-ms"] = str(latency_ms)


def _set_llm_headers(resp: Response, meta: Dict[str, Any]) -> None:
    resp.headers["x-provider"] = meta.get("provider", "")
    resp.headers["x-model"] = meta.get("model", "")
    resp.headers["x-llm-mode"] = meta.get("mode", "")
    usage = meta.get("usage") or {}
    total = usage.get("total_tokens") if isinstance(usage, dict) else None
    if total is not None:
        resp.headers["x-usage-total"] = str(total)


def _problem_json(status: int, title: str, detail: str, type_: str = "about:blank") -> Dict[str, Any]:
    return {"type": type_, "title": title, "status": status, "detail": detail}


def _problem_response(status: int, title: str, detail: str) -> JSONResponse:
    resp = JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=_problem_json(status, title, detail),
    )
    _set_schema_headers(resp)
    return resp


async def _read_body_guarded(request: Request) -> bytes:
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    return body


def _count_placeholders(text: str) -> int:
    return len(_PLACEHOLDER_RE.findall(text or ""))


def _missing_exhibits(text: str) -> List[str]:
    found = {m.upper() for m in _EXHIBIT_RE.findall(text or "")}
    return [e for e in sorted(REQUIRED_EXHIBITS) if e not in found]


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
async def health(response: Response) -> dict:
    """Health endpoint with schema version and rule count."""
    _set_schema_headers(response)
    return {
        "status": "ok",
        "schema": SCHEMA_VERSION,
        "rules_count": _discover_rules_count(),
        "llm": {
            "provider": LLM_CONFIG.provider,
            "model": LLM_CONFIG.model_draft,
            "mode": LLM_CONFIG.mode,
            "timeout_s": LLM_CONFIG.timeout_s,
        },
    }


@router.get("/api/trace/{cid}")
async def api_trace(cid: str, response: Response):
    _set_schema_headers(response)
    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
    return {"status": "ok", "cid": cid, "events": _TRACE.get(cid, [])}


@router.get("/api/trace")
async def api_trace_index(response: Response):
    _set_schema_headers(response)
    _set_std_headers(response, cid="trace-index", xcache="miss", schema=SCHEMA_VERSION)
    return {"status": "ok", "cids": list(_TRACE.keys())}


@router.post("/api/analyze")
async def api_analyze(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    _set_schema_headers(response)
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

    result = _analyze_document(model.text or "")
    if hasattr(result, "model_dump"):
        result = result.model_dump()

    async with _cache_lock:
        IDEMPOTENT_CACHE.put(key, result)

    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return result


# --------------------------------------------------------------------
# Document summary endpoint
# --------------------------------------------------------------------


@router.get("/api/summary")
async def api_summary_get(response: Response, mode: Optional[str] = None):
    _set_schema_headers(response)
    snap = extract_document_snapshot("")
    snap.rules_count = _discover_rules_count()
    _set_std_headers(response, cid="summary:get", xcache="miss", schema=SCHEMA_VERSION)
    return {"status": "ok", "summary": snap.model_dump()}


@router.post("/api/summary")
async def api_summary_post(
    request: Request,
    response: Response,
    x_cid: Optional[str] = Header(None),
    mode: Optional[str] = None,
):
    t0 = _now_ms()
    _set_schema_headers(response)
    try:
        body = await _read_body_guarded(request)
        payload = json.loads(body.decode("utf-8")) if body else {}
    except HTTPException:
        return _problem_response(413, "Payload too large", "Request body exceeds limits")
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    text = str(payload.get("text") or "")
    cid = x_cid or _sha256_hex(str(t0) + text[:128])

    snap = extract_document_snapshot(text)
    snap.rules_count = _discover_rules_count()

    envelope = {"status": "ok", "summary": snap.model_dump()}
    _set_std_headers(
        response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0
    )
    return envelope


# compatibility aliases at root level
@router.get("/summary")
async def summary_get_alias(response: Response, mode: Optional[str] = None):
    _set_schema_headers(response)
    return await api_summary_get(response, mode)


@router.post("/summary")
async def summary_post_alias(
    request: Request, response: Response, x_cid: Optional[str] = Header(None), mode: Optional[str] = None
):
    _set_schema_headers(response)
    return await api_summary_post(request, response, x_cid, mode)


@router.post("/api/gpt/draft")
async def api_gpt_draft(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    _set_schema_headers(response)
    try:
        payload = await request.json()
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")
    if run_gpt_draft:
        cid = x_cid or _sha256_hex(str(t0) + json.dumps(payload or {}, sort_keys=True)[:128])
        try:
            result = await _maybe_await(run_gpt_draft, payload)
        except ProviderTimeoutError as ex:
            meta = {}
            resp = JSONResponse(status_code=503, content={"status": "error", "error_code": "provider_timeout", "detail": str(ex), "meta": meta})
            _set_llm_headers(resp, meta)
            _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
            return resp
        except ProviderAuthError as ex:
            meta = {}
            resp = JSONResponse(status_code=401, content={"status": "error", "error_code": "provider_auth", "detail": ex.detail, "meta": meta})
            _set_llm_headers(resp, meta)
            _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
            return resp
        except ProviderConfigError as ex:
            meta = {}
            resp = JSONResponse(status_code=424, content={"status": "error", "error_code": "llm_unavailable", "detail": ex.detail, "meta": meta})
            _set_llm_headers(resp, meta)
            _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
            return resp

        meta = result.get("meta", {"model": result.get("model")})
        meta.setdefault("model", result.get("model"))
        _set_llm_headers(response, meta)
        _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return {"status": "ok", "draft_text": result.get("text", ""), "meta": meta}

    text = (payload or {}).get("text", "")
    clause_type = (payload or {}).get("clause_type")
    cid = x_cid or _sha256_hex(str(t0) + text[:128])

    meta = LLM_CONFIG.meta()
    if not text.strip():
        resp = JSONResponse(status_code=422, content={"status": "error", "error_code": "bad_input", "detail": "text is empty", "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    if not LLM_CONFIG.valid:
        detail = f"{LLM_CONFIG.provider}: missing {' '.join(LLM_CONFIG.missing)}".strip()
        resp = JSONResponse(status_code=424, content={"status": "error", "error_code": "llm_unavailable", "detail": detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    try:
        result = LLM_SERVICE.draft(text, clause_type, LLM_CONFIG.max_tokens, LLM_CONFIG.temperature, LLM_CONFIG.timeout_s)
    except ProviderTimeoutError as ex:
        meta = {**meta}
        resp = JSONResponse(status_code=503, content={"status": "error", "error_code": "provider_timeout", "detail": str(ex), "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    except ProviderAuthError as ex:
        meta = {**meta}
        resp = JSONResponse(status_code=401, content={"status": "error", "error_code": "provider_auth", "detail": ex.detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    except ProviderConfigError as ex:
        meta = {**meta}
        resp = JSONResponse(status_code=424, content={"status": "error", "error_code": "llm_unavailable", "detail": ex.detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp

    meta = result.meta
    _set_llm_headers(response, meta)
    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return {"status": "ok", "draft_text": result.text, "meta": meta}


@router.post("/api/suggest_edits")
async def api_suggest_edits(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    _set_schema_headers(response)
    try:
        payload = await request.json()
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    text = (payload or {}).get("text", "")
    risk_level = (payload or {}).get("risk_level", "low")
    cid = x_cid or _sha256_hex(str(t0) + text[:128])
    meta = LLM_CONFIG.meta()
    if not text.strip():
        resp = JSONResponse(status_code=422, content={"status": "error", "error_code": "bad_input", "detail": "text is empty", "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    if not LLM_CONFIG.valid:
        detail = f"{LLM_CONFIG.provider}: missing {' '.join(LLM_CONFIG.missing)}".strip()
        resp = JSONResponse(status_code=424, content={"status": "error", "error_code": "llm_unavailable", "detail": detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    try:
        result = LLM_SERVICE.suggest(text, risk_level, LLM_CONFIG.timeout_s)
    except ProviderTimeoutError as ex:
        resp = JSONResponse(status_code=503, content={"status": "error", "error_code": "provider_timeout", "detail": str(ex), "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    except ProviderAuthError as ex:
        resp = JSONResponse(status_code=401, content={"status": "error", "error_code": "provider_auth", "detail": ex.detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    except ProviderConfigError as ex:
        resp = JSONResponse(status_code=424, content={"status": "error", "error_code": "llm_unavailable", "detail": ex.detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp

    meta = result.meta
    _set_llm_headers(response, meta)
    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return {"status": "ok", "suggestions": result.items, "meta": meta}


@router.post("/api/qa-recheck")
async def api_qa_recheck(request: Request, response: Response, x_cid: Optional[str] = Header(None)):
    t0 = _now_ms()
    _set_schema_headers(response)
    try:
        payload = await request.json()
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    text = (payload or {}).get("text", "")
    rules = (payload or {}).get("rules", {})
    cid = x_cid or _sha256_hex(str(t0) + text[:128])
    meta = LLM_CONFIG.meta()
    if not text.strip():
        resp = JSONResponse(status_code=422, content={"status": "error", "error_code": "bad_input", "detail": "text is empty", "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    if not LLM_CONFIG.valid:
        detail = f"{LLM_CONFIG.provider}: missing {' '.join(LLM_CONFIG.missing)}".strip()
        resp = JSONResponse(status_code=424, content={"status": "error", "error_code": "llm_unavailable", "detail": detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    try:
        result = LLM_SERVICE.qa(text, rules, LLM_CONFIG.timeout_s)
    except ProviderTimeoutError as ex:
        resp = JSONResponse(status_code=503, content={"status": "error", "error_code": "provider_timeout", "detail": str(ex), "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    except ProviderAuthError as ex:
        resp = JSONResponse(status_code=401, content={"status": "error", "error_code": "provider_auth", "detail": ex.detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    except ProviderConfigError as ex:
        resp = JSONResponse(status_code=424, content={"status": "error", "error_code": "llm_unavailable", "detail": ex.detail, "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp
    except ValueError as ex:
        _trace_push(cid, {"qa_prompt_debug": True, "unknown_placeholders": getattr(ex, "unknown_placeholders", [])})
        resp = JSONResponse(status_code=500, content={"status": "error", "error_code": "qa_prompt_invalid", "detail": str(ex), "meta": meta})
        _set_llm_headers(resp, meta)
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
        return resp

    meta = result.meta
    _set_llm_headers(response, meta)
    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION, latency_ms=_now_ms() - t0)
    return {"status": "ok", "qa": result.items, "meta": meta}


@router.post("/api/calloff/validate")
async def api_calloff_validate(
    request: Request, response: Response, x_cid: Optional[str] = Header(None)
):
    t0 = _now_ms()
    _set_schema_headers(response)
    try:
        body = await _read_body_guarded(request)
        payload = json.loads(body.decode("utf-8")) if body else {}
    except HTTPException:
        return _problem_response(413, "Payload too large", "Request body exceeds limits")
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    cid = x_cid or _sha256_hex(str(t0) + json.dumps(payload, sort_keys=True)[:128])
    issues = validate_calloff(payload if isinstance(payload, dict) else {})
    _set_std_headers(
        response,
        cid=cid,
        xcache="miss",
        schema=SCHEMA_VERSION,
        latency_ms=_now_ms() - t0,
    )
    return {"status": "ok", "issues": issues}


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
    _set_schema_headers(resp)
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
    _set_schema_headers(response)
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


# --------------------------------------------------------------------
# Panel self-test cases
# --------------------------------------------------------------------
PANEL_SELFTEST = [
    {
        "name": "qa-recheck",
        "method": "POST",
        "path": "/api/qa-recheck",
        "body": {"text": "Hello", "rules": {"R1": "Sample rule"}},
        "expect": {"http": 200, "issues": []},
    }
]
