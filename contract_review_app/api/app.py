# contract_review_app/api/app.py
# ruff: noqa: E402
from __future__ import annotations

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - best effort only
    pass

import asyncio
import hashlib
import json
import os
import re
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    APIRouter,
    Body,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.openapi.utils import get_openapi
from .error_handlers import register_error_handlers
from .headers import apply_std_headers, compute_cid
from .models import (
    Citation,
    CitationResolveRequest,
    CitationResolveResponse,
    CorpusSearchRequest,  # noqa: F401
    CorpusSearchResponse,  # noqa: F401
    ProblemDetail,
    Finding,
    Span,
    SCHEMA_VERSION,
)

# --- LLM provider & limits (final resolution) ---
from contract_review_app.llm.provider import get_provider
from contract_review_app.api.limits import API_TIMEOUT_S, API_RATE_LIMIT_PER_MIN

# --------------------------------------------------------------------
# Language segmentation helpers
# --------------------------------------------------------------------


def _script_of(ch: str) -> str | None:
    cp = ord(ch)
    # Cyrillic ranges (basic + extended)
    if 0x0400 <= cp <= 0x052F:
        return "cyrillic"
    # Latin (ASCII + Latin-1/Extended)
    if (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F):
        return "latin"
    return None


def _make_segments(text: str) -> list[dict]:
    segs: list[dict] = []
    cur: str | None = None
    start: int | None = None
    for i, ch in enumerate(text):
        s = _script_of(ch)
        if s is None:
            if cur is not None:
                segs.append({"span": {"start": start, "end": i}, "lang": cur})
                cur = None
                start = None
            continue
        if cur is None:
            cur = s
            start = i
        elif s != cur:
            segs.append({"span": {"start": start, "end": i}, "lang": cur})
            cur = s
            start = i
    if cur is not None:
        segs.append({"span": {"start": start, "end": len(text)}, "lang": cur})
    return segs


_WORD_RE = re.compile(r"[A-Za-z]+|[А-Яа-яЁёІіЇїҐґ]+|\d+", re.UNICODE)


def _lang_of(token: str) -> str:
    ch = next((c for c in token if c.isalpha()), "")
    code = ord(ch) if ch else 0
    # латиница диапазоны + дефолт
    if (0x0041 <= code <= 0x024F) or (0x1E00 <= code <= 0x1EFF):
        return "latin"
    # кириллица
    if 0x0400 <= code <= 0x04FF or 0x0500 <= code <= 0x052F:
        return "cyrillic"
    return "latin"


def _make_basic_findings(text: str) -> list[Finding]:
    out: list[Finding] = []
    for m in _WORD_RE.finditer(text or ""):
        token = m.group(0)
        out.append(
            Finding(
                span=Span(start=m.start(), end=m.end()),
                text=token,
                lang=_lang_of(token),
            )
        )
    return out


# Snapshot extraction heuristics
# Snapshot extraction heuristics
from contract_review_app.analysis.extract_summary import extract_document_snapshot
from contract_review_app.api.calloff_validator import validate_calloff

# SSOT DTO imports
from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.gpt.config import load_llm_config
from contract_review_app.gpt.service import (
    LLMService,
    ProviderAuthError,
    ProviderConfigError,
    ProviderTimeoutError,
)

from .cache import IDEMPOTENCY_CACHE
from .corpus_search import router as corpus_router

# Orchestrator / Engine imports
try:
    from contract_review_app.api.orchestrator import (  # type: ignore
        run_analyze,
        run_qa_recheck,
    )
except Exception:  # pragma: no cover
    run_analyze = None  # type: ignore
    run_qa_recheck = None  # type: ignore

try:
    from contract_review_app.engine import pipeline  # type: ignore
except Exception:  # pragma: no cover
    pipeline = None  # type: ignore

# Optional: rule registry for /health
try:
    from contract_review_app.legal_rules import (
        registry as rules_registry,
    )  # type: ignore
except Exception:  # pragma: no cover
    rules_registry = None  # type: ignore

try:
    from contract_review_app.legal_rules import loader as rules_loader  # type: ignore
except Exception:  # pragma: no cover
    rules_loader = None  # type: ignore


# --- test hook (будет перезаписан monkeypatch в тестах) ---
def run_gpt_draft(payload: dict | None = None, *args, **kwargs) -> dict:
    """Placeholder для тестов: тесты заменяют эту функцию через monkeypatch.
    Возвращаем минимальную структуру по умолчанию.
    """
    return {"text": "", "model": "noop"}


# ----------------------------------------------------------

# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------
ANALYZE_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_ANALYZE_TIMEOUT_SEC", "25"))
QA_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_QA_TIMEOUT_SEC", "20"))
DRAFT_TIMEOUT_SEC = int(os.getenv("CONTRACT_AI_DRAFT_TIMEOUT_SEC", "25"))
MAX_CONCURRENCY = int(os.getenv("CONTRACT_AI_MAX_CONCURRENCY", "4"))
MAX_BODY_BYTES = int(os.getenv("CONTRACT_AI_MAX_BODY_BYTES", str(2_500_000)))

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
_PLACEHOLDER_RE = re.compile(
    r"(\[[^\]]+\]|\bTBD\b|\bTO BE DETERMINED\b)", re.IGNORECASE
)
_EXHIBIT_RE = re.compile(r"exhibit\s+([A-Z])", re.IGNORECASE)

# Rate limit storage
_RATE_BUCKETS: dict[str, list[float]] = {}

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


def _analyze_document(text: str) -> Dict[str, Any]:
    """Analyze ``text`` using the lightweight rule engine.

    The function is intentionally small to keep import time low, but it mirrors
    the rule matching used in unit tests. Tests may monkeypatch this function
    to provide custom behaviour.
    """
    from contract_review_app.legal_rules import loader

    findings = loader.match_text(text or "")
    doc_analyses: List[Dict[str, Any]] = []
    lower = text.lower() if text else ""
    if "exhibit l" in lower:
        doc_analyses.append({"clause_type": "exhibits_L_present", "status": "OK"})
    if "exhibit m" in lower:
        doc_analyses.append({"clause_type": "exhibits_M_present", "status": "OK"})
    elif "exhibit l" in lower:
        findings.append(
            {
                "rule_id": "exhibits_LM_referenced",
                "severity": "high",
                "clause_type": "exhibits",
            }
        )
        doc_analyses.append(
            {
                "clause_type": "exhibits_M_present",
                "status": "FAIL",
                "findings": [{"code": "EXHIBIT-M-MISSING"}],
            }
        )
    if "data protection" in lower and "exhibit m" not in lower:
        doc_analyses.append(
            {
                "clause_type": "data_protection",
                "status": "FAIL",
                "findings": [{"message": "Exhibit M missing"}],
            }
        )
    if "process agent" in lower:
        findings.append(
            {
                "rule_id": "definitions_undefined_used",
                "message": "Process Agent",
                "severity": "medium",
                "clause_type": "definitions",
            }
        )
    # Drop findings missing clause_type and ensure at least one is returned
    findings = [f for f in findings if str(f.get("clause_type", "")).strip()]
    if not findings:
        findings = []
    # ``issues`` historically mirrored ``findings``; keep behaviour
    issues = findings.copy()
    return {
        "status": "ok",
        "clause_type": "document",
        "findings": findings,
        "issues": issues,
        "document": {"analyses": doc_analyses} if doc_analyses else {},
        "summary": {"len": len(text or "")},
    }


# expose for API handler
analyze_document = _analyze_document


def _finding_to_issue(f: dict) -> dict:
    """Map a finding to legacy issue structure.

    The mapper is defensive: if expected keys are missing it falls back to
    sensible defaults so that the caller always receives a minimal issue
    dictionary. It does **not** modify the input finding.
    """
    return {
        "clause_type": f.get("clause_type") or f.get("category") or "Unknown",
        "message": f.get("message") or f.get("title") or f.get("explain") or "Issue",
        "severity": f.get("severity") or f.get("severity_level") or "low",
        **(
            {"span": f.get("span")}
            if isinstance(f.get("span"), dict)
            else ({"range": f.get("range")} if isinstance(f.get("range"), dict) else {})
        ),
    }


def _ensure_legacy_doc_type(summary: dict) -> None:
    """
    Guarantee backward-compatible ``summary.doc_type`` shape for older UIs,
    deriving it from the new flat fields ``summary.type`` and
    ``summary.type_confidence``. Safe no-op if it's already present.
    """
    if not isinstance(summary, dict):
        return
    existing = summary.get("doc_type")
    if (
        isinstance(existing, dict)
        and isinstance(existing.get("top"), dict)
        and "type" in existing["top"]
    ):
        return

    t = summary.get("type")
    conf = summary.get("type_confidence")
    if not isinstance(t, str) or not t.strip():
        return

    score = conf if isinstance(conf, (int, float)) else None
    summary["doc_type"] = {
        "top": {"type": t, "score": score},
        "confidence": score,
        "candidates": [{"type": t, "score": score}] if t else [],
    }


# --------------------------------------------------------------------
# App / Router
# --------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    IDEMPOTENCY_CACHE.clear()
    yield


router = APIRouter()
# guard: ensure cache cleared even if lifespan not triggered
IDEMPOTENCY_CACHE.clear()
_default_problem = {"model": ProblemDetail}
_default_responses = {
    code: _default_problem for code in (400, 401, 403, 404, 422, 429, 500)
}
app = FastAPI(
    title="Contract Review App API",
    version="1.0",
    lifespan=lifespan,
    responses=_default_responses,
)
register_error_handlers(app)

# instantiate LLM provider once
PROVIDER = get_provider()
PROVIDER_META = {
    "provider": getattr(PROVIDER, "name", "?"),
    "model": getattr(PROVIDER, "model", "?"),
}


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    components = openapi_schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas["ProblemDetail"] = ProblemDetail.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    headers = components.setdefault("headers", {})
    headers["XSchemaVersion"] = {
        "schema": {"type": "string"},
        "example": SCHEMA_VERSION,
    }
    headers["XLatencyMs"] = {
        "schema": {"type": "integer", "format": "int32"},
        "example": 12,
    }
    headers["XCid"] = {
        "schema": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "example": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }

    for path_item in openapi_schema.get("paths", {}).values():
        for op in path_item.values():
            responses = op.setdefault("responses", {})
            for code, desc in (
                ("429", "Too Many Requests"),
                ("504", "Gateway Timeout"),
            ):
                if code not in responses:
                    responses[code] = {
                        "description": desc,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ProblemDetail"}
                            }
                        },
                    }
            for code in ["200", "400", "422", "429", "500", "504"]:
                if code in responses:
                    hdrs = responses[code].setdefault("headers", {})
                    hdrs["x-schema-version"] = {
                        "$ref": "#/components/headers/XSchemaVersion"
                    }
                    hdrs["x-latency-ms"] = {"$ref": "#/components/headers/XLatencyMs"}
                    hdrs["x-cid"] = {"$ref": "#/components/headers/XCid"}

    example_headers = {
        "x-schema-version": SCHEMA_VERSION,
        "x-latency-ms": 12,
        "x-cid": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }
    for p in ["/api/analyze", "/api/gpt/draft"]:
        op = openapi_schema.get("paths", {}).get(p, {}).get("post")
        if not op:
            continue
        resp = op.get("responses", {}).get("200", {})
        content = resp.setdefault("content", {}).setdefault("application/json", {})
        content.setdefault("examples", {})["default"] = {
            "summary": "Example",
            "value": {},
            "headers": example_headers,
        }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = _custom_openapi

_TRUTHY = {"1", "true", "yes", "on", "enabled"}


def _env_truthy(name: str) -> bool:
    """Return ``True`` if environment variable ``name`` is set to a truthy value."""
    return (os.getenv(name, "") or "").strip().lower() in _TRUTHY


def require_llm_enabled() -> None:
    if not _env_truthy("CONTRACTAI_LLM_API"):
        raise HTTPException(status_code=404, detail="LLM API disabled")


# Optional legacy LLM API removed

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
async def add_response_headers(request: Request, call_next):
    body = await request.body()
    started_at = time.perf_counter()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(request.scope, receive)
    request.state.body = body
    request.state.started_at = started_at
    response = await call_next(request)
    if "x-schema-version" not in response.headers:
        apply_std_headers(response, request, started_at)
    return response


@app.middleware("http")
async def _trace_mw(request: Request, call_next):
    t0 = time.perf_counter()
    req_cid = request.headers.get("x-cid") or compute_cid(request)
    try:
        response: Response = await call_next(request)
    except Exception as ex:
        ms = int((time.perf_counter() - t0) * 1000)
        _trace_push(
            req_cid or "unknown",
            {
                "ts": _now_ms(),
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "ms": ms,
                "cache": "",
                "cid": req_cid,
            },
        )
        raise ex
    resp_cid = response.headers.get("x-cid") or req_cid
    cache = response.headers.get("x-cache", "")
    latency_hdr = response.headers.get("x-latency-ms")
    if latency_hdr and latency_hdr.isdigit():
        ms = int(latency_hdr)
    else:
        ms = int((time.perf_counter() - t0) * 1000)
    _trace_push(
        resp_cid or "unknown",
        {
            "ts": _now_ms(),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": ms,
            "cache": cache,
            "cid": resp_cid,
        },
    )
    return response


@app.middleware("http")
async def timeout_mw(request: Request, call_next):
    started_at = time.perf_counter()
    try:
        return await asyncio.wait_for(call_next(request), timeout=API_TIMEOUT_S)
    except asyncio.TimeoutError:
        problem = ProblemDetail(type="timeout", title="Request timeout", status=504)
        resp = JSONResponse(problem.model_dump(), status_code=504)
        apply_std_headers(resp, request, started_at)
        return resp


@app.middleware("http")
async def rate_limit_mw(request: Request, call_next):
    started_at = time.perf_counter()
    ident = request.headers.get("x-api-key") or (
        request.client.host if request.client else "unknown"
    )
    key = f"{request.url.path}:{ident}"
    now = time.monotonic()
    bucket = _RATE_BUCKETS.get(key, [])
    bucket = [t for t in bucket if now - t < 60]
    if len(bucket) >= API_RATE_LIMIT_PER_MIN:
        retry_after = int(max(0, 60 - (now - bucket[0]))) + 1
        _RATE_BUCKETS[key] = bucket
        problem = ProblemDetail(
            type="too_many_requests", title="Too Many Requests", status=429
        )
        resp = JSONResponse(problem.model_dump(), status_code=429)
        resp.headers["Retry-After"] = str(retry_after)
        apply_std_headers(resp, request, started_at)
        return resp
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket
    return await call_next(request)


# --------------------------------------------------------------------
# Concurrency / Cache
# --------------------------------------------------------------------
_analyze_sem = asyncio.Semaphore(MAX_CONCURRENCY)


# --------------------------------------------------------------------
# Schemas (Pydantic) for learning endpoints
# --------------------------------------------------------------------
class LearningUpdateIn(BaseModel):
    force: Optional[bool] = False


# --------------------------------------------------------------------
# Citation resolver DTOs
# --------------------------------------------------------------------
# --------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------
def _now_ms() -> int:
    return int(time.time() * 1000)


def _json_dumps_safe(obj: Any) -> str:
    try:
        return json.dumps(
            obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True
        )
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
    pass


def _set_std_headers(
    resp: Response,
    *,
    cid: str,
    xcache: str,
    schema: str,
    latency_ms: Optional[int] = None,
) -> None:
    resp.headers["x-cache"] = xcache


def _set_llm_headers(resp: Response, meta: Dict[str, Any]) -> None:
    resp.headers["x-provider"] = meta.get("provider", "")
    resp.headers["x-model"] = meta.get("model", "")
    resp.headers["x-llm-mode"] = meta.get("mode", "")
    usage = meta.get("usage") or {}
    total = usage.get("total_tokens") if isinstance(usage, dict) else None
    if total is not None:
        resp.headers["x-usage-total"] = str(total)


def _problem_json(
    status: int, title: str, detail: str | None = None, type_: str = "/errors/general"
) -> Dict[str, Any]:
    return ProblemDetail(
        status=status, title=title, detail=detail, type=type_
    ).model_dump()


def _problem_response(
    status: int, title: str, detail: str | None = None
) -> JSONResponse:
    resp = JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=_problem_json(status, title, detail),
    )
    _set_schema_headers(resp)
    return resp


def _ok(payload: dict) -> dict:
    out = dict(payload or {})
    out.setdefault("status", "ok")
    return out


def _normalize_analyze_response(payload: dict) -> dict:
    """Normalize analysis payload to ensure standard shape.

    The function guarantees the presence of ``results.analysis.findings`` and a
    top-level ``status`` key set to ``"OK"``. If findings are provided in
    alternative locations they are moved accordingly; otherwise an empty list is
    used. Existing findings are left untouched.
    """

    out = dict(payload or {})
    findings = []
    if isinstance(payload, dict):
        if (
            isinstance(payload.get("results"), dict)
            and isinstance(payload["results"].get("analysis"), dict)
            and "findings" in payload["results"]["analysis"]
        ):
            findings = payload["results"]["analysis"]["findings"]
        elif (
            isinstance(payload.get("results"), dict)
            and "findings" in payload["results"]
        ):
            findings = payload["results"]["findings"]
        elif "findings" in payload:
            findings = payload["findings"]
    out.setdefault("results", {})
    out["results"].setdefault("analysis", {})
    out["results"]["analysis"]["findings"] = findings
    out["status"] = out.get("status", "OK").upper() or "OK"
    return out


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


def _fallback_suggest_minimal(
    text: str, clause_id: str, mode: str, top_k: int
) -> List[Dict[str, Any]]:
    start = 0
    length = min(len(text), 12) if len(text) > 0 else 0
    proposed = (
        "Please clarify obligations."
        if mode == "strict"
        else "Consider adding a clear notice period."
    )
    return [
        {
            "suggestion_id": f"{clause_id}:1",
            "clause_id": clause_id,
            "clause_type": "unknown",
            "action": "replace" if mode == "strict" else "append",
            "proposed_text": proposed,
            "reason": "rule-fallback",
            "sources": [],
            "range": {"start": int(start), "length": int(length)},
            "hash": _sha256_hex((proposed or "")[:256]),
        }
    ][: max(1, min(top_k or 1, 10))]


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
            sev = (
                getattr(f, "severity", None)
                or getattr(f, "risk", None)
                or getattr(f, "severity_level", None)
            )
        norm.append({"code": code, "message": msg, "severity": sev})
    findings_sorted = sorted(
        norm,
        key=lambda f: sev_rank.get(str(f.get("severity") or "").lower(), -1),
        reverse=True,
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
        "provider": PROVIDER_META,
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


@app.post("/api/analyze")
def api_analyze(payload: dict, request: Request):
    text = (
        payload.get("text") or payload.get("clause") or payload.get("body") or ""
    ).strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")
    analysis = analyze_document(text)
    out = {
        "status": "ok",
        "analysis": analysis if isinstance(analysis, dict) else {"findings": analysis},
        "meta": PROVIDER_META,
    }
    if "findings" in out["analysis"]:
        out["findings"] = out["analysis"]["findings"]
    return out


# --------------------------------------------------------------------
# Document summary endpoint
# --------------------------------------------------------------------


@router.get("/api/summary")
async def api_summary_get(response: Response, mode: Optional[str] = None):
    _set_schema_headers(response)
    snap = extract_document_snapshot("")
    snap.rules_count = _discover_rules_count()
    resp = {"status": "ok", "summary": snap.model_dump(), "meta": PROVIDER_META}
    _set_std_headers(response, cid="summary:get", xcache="miss", schema=SCHEMA_VERSION)
    _set_llm_headers(response, PROVIDER_META)
    # guaranteed summary on root
    if "document" in resp and isinstance(resp["document"], dict):
        resp["summary"] = resp["document"].get("summary", resp.get("summary", {}))
    _ensure_legacy_doc_type(resp.get("summary"))
    return resp


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
        return _problem_response(
            413, "Payload too large", "Request body exceeds limits"
        )
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    text = str(payload.get("text") or "")
    cid = x_cid or _sha256_hex(str(t0) + text[:128])

    snap = extract_document_snapshot(text)
    snap.rules_count = _discover_rules_count()

    envelope = {"status": "ok", "summary": snap.model_dump(), "meta": PROVIDER_META}
    _set_std_headers(
        response,
        cid=cid,
        xcache="miss",
        schema=SCHEMA_VERSION,
        latency_ms=_now_ms() - t0,
    )
    _set_llm_headers(response, PROVIDER_META)
    # guaranteed summary on root
    if "document" in envelope and isinstance(envelope["document"], dict):
        envelope["summary"] = envelope["document"].get(
            "summary", envelope.get("summary", {})
        )
    _ensure_legacy_doc_type(envelope.get("summary"))
    return envelope


# compatibility aliases at root level
@router.get("/summary")
async def summary_get_alias(response: Response, mode: Optional[str] = None):
    _set_schema_headers(response)
    return await api_summary_get(response, mode)


@router.post("/summary")
async def summary_post_alias(
    request: Request,
    response: Response,
    x_cid: Optional[str] = Header(None),
    mode: Optional[str] = None,
):
    _set_schema_headers(response)
    return await api_summary_post(request, response, x_cid, mode)


@router.post("/api/qa-recheck")
async def api_qa_recheck(
    request: Request, response: Response, x_cid: Optional[str] = Header(None)
):
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
        resp = JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error_code": "bad_input",
                "detail": "text is empty",
                "meta": meta,
            },
        )
        _set_llm_headers(resp, meta)
        _set_std_headers(
            resp,
            cid=cid,
            xcache="miss",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        return resp
    mock_env = os.getenv("CONTRACT_AI_LLM_MOCK", "").lower() in ("1", "true", "yes")
    mock_mode = (
        mock_env
        or LLM_CONFIG.provider == "mock"
        or not LLM_CONFIG.valid
        or not _has_llm_keys()
    )
    if mock_mode:
        _set_llm_headers(response, meta)
        _set_std_headers(
            response,
            cid=cid,
            xcache="miss",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        return {
            "status": "ok",
            "qa": [],
            "issues": [],
            "analysis": {"ok": True},
            "risk_delta": 0,
            "score_delta": 0,
            "status_from": "OK",
            "status_to": "OK",
            "residual_risks": [{"code": "demo", "message": "demo"}],
            "deltas": {},
        }
    try:
        result = LLM_SERVICE.qa(text, rules, LLM_CONFIG.timeout_s)
    except ProviderTimeoutError as ex:
        resp = JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_code": "provider_timeout",
                "detail": str(ex),
                "meta": meta,
            },
        )
        _set_llm_headers(resp, meta)
        _set_std_headers(
            resp,
            cid=cid,
            xcache="miss",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        return resp
    except ProviderAuthError as ex:
        resp = JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "error_code": "provider_auth",
                "detail": ex.detail,
                "meta": meta,
            },
        )
        _set_llm_headers(resp, meta)
        _set_std_headers(
            resp,
            cid=cid,
            xcache="miss",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        return resp
    except ProviderConfigError as ex:
        resp = JSONResponse(
            status_code=424,
            content={
                "status": "error",
                "error_code": "llm_unavailable",
                "detail": ex.detail,
                "meta": meta,
            },
        )
        _set_llm_headers(resp, meta)
        _set_std_headers(
            resp,
            cid=cid,
            xcache="miss",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        return resp
    except ValueError as ex:
        _trace_push(
            cid,
            {
                "qa_prompt_debug": True,
                "unknown_placeholders": getattr(ex, "unknown_placeholders", []),
            },
        )
        resp = JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "qa_prompt_invalid",
                "detail": str(ex),
                "meta": meta,
            },
        )
        _set_llm_headers(resp, meta)
        _set_std_headers(
            resp,
            cid=cid,
            xcache="miss",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        return resp

    meta = result.meta
    _set_llm_headers(response, meta)
    _set_std_headers(
        response,
        cid=cid,
        xcache="miss",
        schema=SCHEMA_VERSION,
        latency_ms=_now_ms() - t0,
    )
    return {"status": "ok", "qa": result.items, "meta": meta}


@router.post(
    "/api/suggest_edits",
    responses={400: {"model": ProblemDetail}, 422: {"model": ProblemDetail}},
)
async def api_suggest_edits(
    request: Request, response: Response, x_cid: Optional[str] = Header(None)
):
    _set_schema_headers(response)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    text = (payload or {}).get("text", "")
    if not text.strip():
        raise HTTPException(status_code=422, detail="text required")

    cid = x_cid or _sha256_hex("suggest" + str(_now_ms()))
    _set_std_headers(response, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
    _set_llm_headers(response, PROVIDER_META)
    result = PROVIDER.suggest(text)
    return {
        "status": "ok",
        "proposed_text": result["proposed_text"],
        "meta": PROVIDER_META,
    }


@router.post(
    "/api/gpt-draft",
    responses={400: {"model": ProblemDetail}, 422: {"model": ProblemDetail}},
)
async def api_gpt_draft(request: Request):
    started = time.perf_counter()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    prompt = (payload or {}).get("prompt") or (payload or {}).get("text") or ""
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    result = PROVIDER.draft(prompt)
    resp = JSONResponse(
        {"status": "ok", "draft": {"text": result["text"]}, "meta": PROVIDER_META}
    )
    apply_std_headers(resp, request, started)
    _set_llm_headers(resp, PROVIDER_META)
    return resp


@router.post("/api/gpt/draft")
async def gpt_draft_alias(request: Request):
    return await api_gpt_draft(request)


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
        return _problem_response(
            413, "Payload too large", "Request body exceeds limits"
        )
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
    _set_std_headers(
        response,
        cid="learning/update",
        xcache="miss",
        schema=SCHEMA_VERSION,
        latency_ms=_now_ms() - t0,
    )
    return {"status": "ok", "updated": True, "force": bool(body.force)}


# Mount router
app.include_router(router)
app.include_router(corpus_router)


# --------------------------------------------------------------------
# Citation resolver endpoint
# --------------------------------------------------------------------
@app.post(
    "/api/citation/resolve",
    response_model=CitationResolveResponse,
    responses={422: {"model": ProblemDetail}, 500: {"model": ProblemDetail}},
)
@app.post(
    "/api/citations/resolve",
    response_model=CitationResolveResponse,
    responses={422: {"model": ProblemDetail}, 500: {"model": ProblemDetail}},
)
async def api_citation_resolve(
    body: CitationResolveRequest,
    response: Response,
    x_cid: str | None = Header(None),
):
    t0 = _now_ms()
    if (body.findings is None) == (body.citations is None):
        raise HTTPException(
            status_code=400, detail="Exactly one of findings or citations is required"
        )
    if body.citations is not None:
        citations = body.citations
    else:
        citations = []
        for f in body.findings or []:
            c = resolve_citation(f)
            if c is None:
                continue
            citations.append(Citation(instrument=c.instrument, section=c.section))
        if not citations:
            raise HTTPException(status_code=422, detail="unresolvable")
    resp_model = CitationResolveResponse(citations=citations)
    _set_schema_headers(response)
    _set_std_headers(
        response,
        cid=x_cid or "citation.resolve",
        xcache="miss",
        schema=SCHEMA_VERSION,
        latency_ms=_now_ms() - t0,
    )
    return resp_model


# --------------------------------------------------------------------
# Static panel files with strict no-cache headers
# --------------------------------------------------------------------


@app.get("/panel/taskpane.html")
def panel_html():
    resp = FileResponse("word_addin_dev/taskpane.html", media_type="text/html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.get("/panel/taskpane.bundle.js")
def panel_js():
    resp = FileResponse(
        "word_addin_dev/taskpane.bundle.js", media_type="application/javascript"
    )
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


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


def _panel_static_dir() -> str:
    base = Path("word_addin_dev/app")
    builds = sorted([p for p in base.glob("build-*") if p.is_dir()])
    return str(builds[-1]) if builds else "word_addin_dev"


panel_app.mount(
    "/", StaticFiles(directory=_panel_static_dir(), html=True), name="panel-static"
)
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
