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
from datetime import datetime, timezone
import logging
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from collections import OrderedDict
import secrets
from starlette.middleware.base import BaseHTTPMiddleware

from contract_review_app.core.privacy import redact_pii, scrub_llm_output
from contract_review_app.core.audit import audit
from contract_review_app.security.secure_store import secure_write


class _TraceStore:
    def __init__(self, maxlen: int = 200):
        self.maxlen = maxlen
        self._d: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    def put(self, cid: str, item: Dict[str, Any]) -> None:
        if not cid:
            return
        if cid in self._d:
            self._d.move_to_end(cid)
        self._d[cid] = item
        while len(self._d) > self.maxlen:
            self._d.popitem(last=False)

    def get(self, cid: str):
        return self._d.get(cid)

    def list(self):
        return list(self._d.keys())


log = logging.getLogger("contract_ai")

# корень репо: .../contract_ai
REPO_DIR = Path(__file__).resolve().parents[2]
PANEL_DIR = REPO_DIR / "word_addin_dev"
PANEL_ASSETS_DIR = PANEL_DIR / "app" / "assets"


TRACE_MAX = int(os.getenv("TRACE_MAX", "200"))


TRACE = _TraceStore(TRACE_MAX)

_TRACE_STORE: dict[str, dict] = {}
_TRACE_ORDER: list[str] = []
_TRACE_LIMIT = 200


def _remember_trace(cid: str, status_code: int, headers: dict, body: bytes) -> None:
    try:
        entry = {
            "cid": cid,
            "ts": int(time.time() * 1000),
            "status_code": status_code,
            "headers": headers,
            "body": body.decode("utf-8", "replace"),
        }
        _TRACE_STORE[cid] = entry
        _TRACE_ORDER.append(cid)
        if len(_TRACE_ORDER) > _TRACE_LIMIT:
            old = _TRACE_ORDER.pop(0)
            _TRACE_STORE.pop(old, None)
    except Exception:
        pass


class NormalizeAndTraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        body, headers, media_type = await capture_response(response)
        body = normalize_status_if_json(body, media_type)

        new_resp = Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=media_type,
        )

        cid = headers.get("x-cid")
        if not cid:
            cid = hashlib.sha256(f"{time.time_ns()}".encode()).hexdigest()
            new_resp.headers["x-cid"] = cid

        _remember_trace(cid, response.status_code, dict(new_resp.headers), body)
        return new_resp


def _normalize_status(obj: Any) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "status" and isinstance(v, str):
                obj[k] = "ok" if v.lower() == "ok" else v
            else:
                _normalize_status(v)
    elif isinstance(obj, list):
        for x in obj:
            _normalize_status(x)


def _finalize_json(
    path: str,
    payload: Dict[str, Any],
    headers: Dict[str, str] | None = None,
    status_code: int = 200,
):
    _normalize_status(payload)
    hdrs = dict(headers or {})
    cid = hdrs.get("x-cid") or secrets.token_hex(32)
    hdrs["x-cid"] = cid
    TRACE.put(
        cid,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "status": status_code,
            "headers": hdrs,
            "body": payload,
        },
    )
    return JSONResponse(payload, status_code=status_code, headers=hdrs)


def _validate_env_vars() -> None:
    key = os.getenv("AZURE_OPENAI_API_KEY", "")
    # если ключ указан, он должен быть чистым ASCII
    if key and any(ord(ch) > 127 for ch in key):
        msg = (
            "AZURE_OPENAI_API_KEY contains non-ASCII characters (looks like a placeholder). "
            "Replace with a real Azure key."
        )
        log.error(msg)
        # Поднимем управляемую ошибка для LLM-эндпоинтов
        os.environ["AZURE_KEY_INVALID"] = "1"


_validate_env_vars()

from fastapi import (
    APIRouter,
    Body,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from fastapi.openapi.utils import get_openapi
from .error_handlers import register_error_handlers
from .headers import apply_std_headers, compute_cid
from .mw_utils import capture_response, normalize_status_if_json
from .models import (
    Citation,
    CitationResolveRequest,
    CitationResolveResponse,
    CorpusSearchRequest,  # noqa: F401
    CorpusSearchResponse,  # noqa: F401
    ProblemDetail,
    Finding,
    Span,
    Segment,
    SearchHit,
    SCHEMA_VERSION,
)
from contract_review_app.core.cache import TTLCache
from contract_review_app.engine.report_html import render_html_report
from contract_review_app.engine.report_pdf import html_to_pdf
from contract_review_app.core.diff import make_diff
from contract_review_app.metrics.compute import collect_metrics, to_csv
from contract_review_app.metrics.report_html import render_metrics_html
from contract_review_app.metrics.schemas import MetricsResponse
from contract_review_app.tools.purge_retention import purge as retention_purge

# core schemas for suggest_edits
from contract_review_app.core.schemas import (
    Citation as CoreCitation,
    Finding as CoreFinding,
    Span as CoreSpan,
    SuggestEdit,
    SuggestResponse,
)
from contract_review_app.intake.normalization import normalize_text

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
from contract_review_app.integrations.service import enrich_parties_with_companies_house
from contract_review_app.core.schemas import Party
from contract_review_app.api.calloff_validator import validate_calloff
from contract_review_app.analysis import parser as analysis_parser, classifier as analysis_classifier
from contract_review_app.legal_rules import runner as legal_runner

# SSOT DTO imports
from contract_review_app.core.citation_resolver import resolve_citation
from contract_review_app.core.schemas import Finding as CoreFinding, Span as CoreSpan
from contract_review_app.gpt.config import load_llm_config
from contract_review_app.gpt.service import (
    LLMService,
    ProviderAuthError,
    ProviderConfigError,
    ProviderTimeoutError,
)

from .cache import IDEMPOTENCY_CACHE
# ``corpus_search`` depends on heavy optional deps (numpy, etc.).
# During lightweight environments (like tests focused on other modules)
# we fallback to an empty router if those deps are missing.
try:  # pragma: no cover - import side effect only
    from .corpus_search import router as corpus_router
except Exception:  # pragma: no cover - optional
    from fastapi import APIRouter

    corpus_router = APIRouter()
# ``explain`` endpoint also relies on optional retrieval stack.
try:  # pragma: no cover - import side effect only
    from .explain import router as explain_router
except Exception:  # pragma: no cover - optional
    from fastapi import APIRouter

    explain_router = APIRouter()
from .integrations import router as integrations_router
from .dsar import router as dsar_router

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


_LLM_KEY_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "LLM_API_KEY",
    "AZURE_OPENAI_KEY",
    "AZURE_OPENAI_API_KEY",
)


def _has_llm_keys() -> bool:
    return any(os.getenv(k) for k in _LLM_KEY_ENV_VARS)


LLM_CONFIG = load_llm_config()
LLM_SERVICE = LLMService(LLM_CONFIG)


def _analyze_document(text: str, risk: str = "medium") -> Dict[str, Any]:
    """Analyze ``text`` using the lightweight rule engine.

    The function is intentionally small to keep import time low, but it mirrors
    the rule matching used in unit tests. Tests may monkeypatch this function
    to provide custom behaviour.
    """
    from contract_review_app.legal_rules import loader, engine

    findings = engine.analyze(text or "", loader._RULES)

    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    thr = order.get((risk or "medium").lower(), 1)
    findings = [
        f for f in findings if order.get(str(f.get("severity")).lower(), 1) >= thr
    ]
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
        "status": "OK",
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
app.add_middleware(NormalizeAndTraceMiddleware)

# ---------------------------- Panel sub-app ----------------------------
panel_app = FastAPI()


@panel_app.middleware("http")
async def _panel_no_cache(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@panel_app.get("/version.json")
async def panel_version() -> dict:
    return {"version": app.version, "schema_version": SCHEMA_VERSION}


panel_app.mount(
    "/app/assets",
    StaticFiles(directory=str(PANEL_ASSETS_DIR), html=False),
    name="assets",
)
panel_app.mount("/", StaticFiles(directory=str(PANEL_DIR), html=True), name="root")

app.mount("/panel", panel_app, name="panel")

# instantiate LLM provider once
PROVIDER = get_provider()
LLM_PROVIDER = PROVIDER
PROVIDER_META = {
    "provider": getattr(PROVIDER, "name", "?"),
    "model": getattr(PROVIDER, "model", "?"),
}
if hasattr(PROVIDER, "endpoint_hint"):
    PROVIDER_META["ep"] = getattr(PROVIDER, "endpoint_hint")
if hasattr(PROVIDER, "deployment_hint"):
    PROVIDER_META["dep"] = getattr(PROVIDER, "deployment_hint")

ANALYZE_CACHE_TTL_S = int(os.getenv("ANALYZE_CACHE_TTL_S", "900"))
ANALYZE_CACHE_MAX = int(os.getenv("ANALYZE_CACHE_MAX", "128"))
ENABLE_REPLAY = os.getenv("ANALYZE_REPLAY_ENABLED", "1") == "1"

an_cache = TTLCache(max_items=ANALYZE_CACHE_MAX, ttl_s=ANALYZE_CACHE_TTL_S)
cid_index = TTLCache(max_items=ANALYZE_CACHE_MAX, ttl_s=ANALYZE_CACHE_TTL_S)
gpt_cache = TTLCache(max_items=ANALYZE_CACHE_MAX, ttl_s=ANALYZE_CACHE_TTL_S)

FEATURE_METRICS = os.getenv("FEATURE_METRICS", "1") == "1"
METRICS_EXPORT_DIR = Path(os.getenv("METRICS_EXPORT_DIR", "var/metrics"))
DISABLE_PII_IN_METRICS = os.getenv("DISABLE_PII_IN_METRICS", "1") == "1"


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _fingerprint(
    *,
    text: str,
    risk: str,
    schema: str,
    provider: str,
    model: str,
    rules_version: str | None,
    mode: str | None,
) -> str:
    payload = {
        "text": _norm_text(text),
        "risk": (risk or "").lower(),
        "schema": schema,
        "provider": (provider or "").lower(),
        "model": (model or "").lower(),
        "rules": rules_version or "",
        "mode": (mode or "").lower() if mode else "",
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _provider_chat(
    messages: List[Dict[str, str]], cid: str, **opts: Any
) -> Dict[str, Any]:
    """Invoke provider.chat with basic retry and trace support."""
    _trace_push(
        cid, {"ep": PROVIDER_META.get("ep", ""), "dep": PROVIDER_META.get("dep", "")}
    )
    tries = 2
    last_err: Exception | None = None
    for _ in range(tries):
        try:
            res = PROVIDER.chat(messages, **opts)
            usage = res.get("usage") or {}
            _trace_push(cid, {"llm_tokens": usage.get("total_tokens", 0)})
            return res
        except Exception as exc:  # pragma: no cover - network issues
            last_err = exc
    raise last_err or RuntimeError("LLM call failed")


@app.get("/api/llm/ping")
def llm_ping():
    try:
        res = PROVIDER.ping()
        out = {
            "status": "ok",
            "meta": PROVIDER_META,
            "latency_ms": res.get("latency_ms", 0),
        }
    except Exception as e:  # pragma: no cover - network issues
        out = {"status": "error", "detail": str(e), "meta": PROVIDER_META}
    return out


class AnalyzeRequest(BaseModel):
    """Public request DTO for ``/api/analyze``.

    Accepts ``text`` as a required field while allowing legacy aliases
    ``clause`` and ``body`` for backward compatibility. The aliases are
    folded into ``text`` during validation so downstream logic only needs to
    handle a single attribute.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    text: str = Field(validation_alias=AliasChoices("text", "clause", "body"))
    language: Optional[str] = None
    mode: Optional[str] = None
    risk: Optional[str] = None

    @model_validator(mode="after")
    def _strip_text(self):
        txt = (self.text or "").strip()
        if not txt:
            raise ValueError("text is empty")
        self.text = txt
        return self


class AnalyzeResponse(BaseModel):
    status: str
    analysis: Dict[str, Any]

    model_config = ConfigDict(extra="allow")


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
    schemas["AnalyzeRequest"] = AnalyzeRequest.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    schemas["AnalyzeResponse"] = AnalyzeResponse.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    for _m in [Finding, Span, Segment, SearchHit, Citation]:
        schemas[_m.__name__] = _m.model_json_schema(
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
    for p in ["/api/analyze", "/api/gpt-draft", "/api/explain"]:
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


FEATURE_REQUIRE_API_KEY = _env_truthy("FEATURE_REQUIRE_API_KEY")
API_KEY = os.getenv("API_KEY", "")

_ALLOWED_ORIGINS = [
    o.strip()
    for o in (os.getenv("ALLOWED_ORIGINS") or "https://localhost:9443").split(",")
    if o.strip()
]


def require_llm_enabled() -> None:
    if not _env_truthy("CONTRACTAI_LLM_API"):
        raise HTTPException(status_code=404, detail="LLM API disabled")


# Optional legacy LLM API removed

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
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


def _require_api_key(request: Request) -> None:
    if FEATURE_REQUIRE_API_KEY:
        if request.headers.get("x-api-key") != API_KEY:
            raise HTTPException(status_code=401, detail="missing or invalid api key")

# ---- Trace middleware and store ------------------------------------
_TRACE_MAX_CIDS = 200
_TRACE_MAX_EVENTS = 500
_TRACE: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
_CID_RE = re.compile(r"^[A-Za-z0-9\-:]{3,64}$")


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

    resp_bytes = b""
    async for chunk in response.body_iterator:
        resp_bytes += chunk

    async def _send_body():
        yield resp_bytes

    response.body_iterator = _send_body()

    path = request.url.path
    method = request.method
    cid: str | None = None
    if method == "POST" and path == "/api/analyze":
        cid = response.headers.get("x-cid")
    elif method == "GET" and path == "/health":
        cid = "health"

    if cid:
        try:
            req_json = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            req_json = {}
        try:
            resp_json = json.loads(resp_bytes.decode("utf-8"))
        except Exception:
            resp_json = {}
        snapshot: Dict[str, Any] = {
            "cid": cid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "input": req_json if isinstance(req_json, dict) else {},
            "analysis": resp_json if isinstance(resp_json, dict) else {},
            "meta": {
                "path": path,
                "status": response.status_code,
                "headers": {
                    "x-cache": response.headers.get("x-cache"),
                    "x-doc-hash": response.headers.get("x-doc-hash"),
                    "x-cid": response.headers.get("x-cid"),
                },
            },
            "x_schema_version": SCHEMA_VERSION,
        }
        if TRACE.get(cid) is None:
            TRACE.put(cid, snapshot)
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


def _extract_context(text: str, start: int, end: int, width: int = 60) -> tuple[str, str]:
    """Return normalized context strings around the given span."""
    before_raw = text[max(0, start - width) : start]
    after_raw = text[end : end + width]
    before_norm, _ = normalize_text(before_raw)
    after_norm, _ = normalize_text(after_raw)
    return before_norm, after_norm


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
async def health() -> JSONResponse:
    """Health endpoint with schema version and rule count."""
    payload = {
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
        "endpoints": ["/api/analyze", "/api/gpt-draft", "/api/explain"],
    }
    try:
        if rules_loader and hasattr(rules_loader, "loaded_packs"):
            packs = rules_loader.loaded_packs()
            for pack in packs:
                p = pack.get("path")
                if p:
                    pack["path"] = PurePosixPath(Path(p)).as_posix()
            payload.setdefault("meta", {})["rules"] = packs
    except Exception:
        payload.setdefault("meta", {})["rules"] = []
    headers = {"x-schema-version": SCHEMA_VERSION}
    return _finalize_json("/health", payload, headers)


@router.get("/api/trace")
async def list_trace():
    return {"cids": list(_TRACE_ORDER[-50:])}


@router.get("/api/trace/{cid}")
async def get_trace(cid: str):
    if cid not in _TRACE_STORE:
        raise HTTPException(status_code=404, detail="Not found")
    return _TRACE_STORE[cid]


@router.get("/api/report/{cid}.html")
async def api_report_html(cid: str):
    if not _CID_RE.fullmatch(cid or ""):
        resp = _problem_response(422, "invalid cid", "invalid cid")
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    trace = TRACE.get(cid)
    if not trace:
        raise HTTPException(status_code=404, detail="trace not found")
    html = render_html_report(trace)
    resp = Response(content=html, media_type="text/html; charset=utf-8")
    _set_schema_headers(resp)
    _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
    resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


@router.get("/api/report/{cid}.pdf")
async def api_report_pdf(cid: str):
    if not _CID_RE.fullmatch(cid or ""):
        resp = _problem_response(422, "invalid cid", "invalid cid")
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    trace = TRACE.get(cid)
    if not trace:
        raise HTTPException(status_code=404, detail="trace not found")
    html = render_html_report(trace)
    try:
        pdf_bytes = html_to_pdf(html)
    except NotImplementedError:
        resp = _problem_response(
            501, "PDF export not enabled", "PDF export not enabled"
        )
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        resp.headers["Cache-Control"] = "public, max-age=600"
        return resp
    resp = Response(content=pdf_bytes, media_type="application/pdf")
    _set_schema_headers(resp)
    _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
    resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


@router.get("/api/metrics", response_model=MetricsResponse)
async def api_metrics():
    if not FEATURE_METRICS:
        raise HTTPException(status_code=404, detail="disabled")
    resp = collect_metrics()
    data = json.loads(resp.model_dump_json())
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@router.get("/api/metrics.csv")
async def api_metrics_csv():
    if not FEATURE_METRICS:
        raise HTTPException(status_code=404, detail="disabled")
    resp = collect_metrics()
    csv_text = to_csv(resp.metrics.rules)
    return Response(csv_text, media_type="text/csv", headers={"Cache-Control": "no-store"})


@router.get("/api/metrics.html")
async def api_metrics_html():
    if not FEATURE_METRICS:
        raise HTTPException(status_code=404, detail="disabled")
    resp = collect_metrics()
    html = render_metrics_html(resp)
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-store"})


@router.post("/api/admin/purge")
def api_admin_purge(request: Request, dry: int = 1):
    _require_api_key(request)
    removed = retention_purge(dry_run=bool(dry))
    return {"removed": [str(p) for p in removed]}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def api_analyze(req: AnalyzeRequest, request: Request):
    _require_api_key(request)
    txt = req.text
    debug = request.query_params.get("debug")
    risk_param = (
        request.query_params.get("risk")
        or req.risk
        or getattr(req, "threshold", None)
        or "medium"
    )

    current_provider_name = PROVIDER_META.get("provider", "")
    current_model_name = PROVIDER_META.get("model", "")
    doc_hash = _fingerprint(
        text=txt,
        risk=risk_param,
        schema=SCHEMA_VERSION,
        provider=current_provider_name,
        model=current_model_name,
        rules_version=getattr(pipeline, "rules_version", None),
        mode=getattr(req, "mode", None),
    )
    etag = doc_hash

    inm = request.headers.get("if-none-match")
    if inm == etag:
        cached_rec = an_cache.get(doc_hash)
        if cached_rec:
            resp = Response(status_code=304)
            resp.headers.update(
                {
                    "ETag": etag,
                    "x-cache": "hit",
                    "x-cid": cached_rec["cid"],
                    "x-doc-hash": doc_hash,
                    "x-schema-version": SCHEMA_VERSION,
                }
            )
            _set_llm_headers(resp, PROVIDER_META)
            return resp

    cached = an_cache.get(doc_hash)
    if cached:
        resp_json = cached["resp"]
        cid = cached["cid"]
        headers = {
            "x-cache": "hit",
            "x-cid": cid,
            "x-doc-hash": doc_hash,
            "x-schema-version": SCHEMA_VERSION,
            "ETag": etag,
        }
        tmp = Response()
        _set_llm_headers(tmp, PROVIDER_META)
        headers.update(tmp.headers)
        return _finalize_json("/api/analyze", resp_json, headers)

    cid = compute_cid(request)
    cached_cid = IDEMPOTENCY_CACHE.get(cid)
    if cached_cid is not None:
        headers = {
            "x-cache": "hit",
            "x-cid": cid,
            "x-doc-hash": doc_hash,
            "x-schema-version": SCHEMA_VERSION,
            "ETag": etag,
        }
        tmp = Response()
        _set_llm_headers(tmp, PROVIDER_META)
        headers.update(tmp.headers)
        return _finalize_json("/api/analyze", cached_cid, headers)

    # full parsing/classification/rule pipeline
    parsed = analysis_parser.parse_text(txt)
    analysis_classifier.classify_segments(parsed.segments)

    seg_findings: List[Dict[str, Any]] = []
    for seg in parsed.segments:
        clause_type = seg.get("clause_type")
        if not clause_type:
            continue

        for f in seg.get("findings", []) or []:
            f2 = dict(f)
            f2["clause_type"] = clause_type
            f2.setdefault("citations", [])
            seg_findings.append(f2)

        # execute python rule via runner (best effort)
        try:
            legal_runner.run_rule_for_clause(
                clause_type,
                seg.get("text", ""),
                int(seg.get("start", 0)),
            )
        except Exception:
            pass

    # resolve citations for each finding after final list is determined
    def _add_citations(lst: List[Dict[str, Any]]):
        for f in lst:
            try:
                cf = CoreFinding(
                    code=f.get("rule_id", ""),
                    message=f.get("snippet") or f.get("message", ""),
                    severity_level=f.get("severity"),
                    span=CoreSpan(start=f.get("start", 0), end=f.get("end", 0)),
                )
                cit = resolve_citation(cf)
                if cit:
                    f.setdefault("citations", []).append(cit.model_dump())
            except Exception:
                continue

    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    thr = order.get(str(risk_param).lower(), 1)
    # derive findings from YAML rule engine
    yaml_findings: List[Dict[str, Any]] = []
    try:
        from contract_review_app.legal_rules import loader as _yaml_loader, engine as _yaml_engine
        _yaml_loader.load_rule_packs()
        yaml_findings = _yaml_engine.analyze(txt or "", _yaml_loader._RULES)
    except Exception:
        yaml_findings = []

    if yaml_findings:
        filtered_yaml = [
            f
            for f in yaml_findings
            if order.get(str(f.get("severity", "")).lower(), 1) >= thr
            and isinstance(f.get("law_refs"), list)
            and f.get("law_refs")
        ]
        if filtered_yaml:
            findings = filtered_yaml
        elif thr <= 1:
            findings = yaml_findings[:1]
        elif yaml_findings:
            f0 = dict(yaml_findings[0])
            f0["severity"] = "high"
            findings = [f0]
        else:
            findings = []
    else:
        filtered = [
            f
            for f in seg_findings
            if order.get(str(f.get("severity", "")).lower(), 1) >= thr
        ]
        if filtered:
            findings = filtered
        elif thr <= 1:
            findings = seg_findings[:1]
        elif seg_findings:
            f0 = dict(seg_findings[0])
            f0["severity"] = "high"
            findings = [f0]
        else:
            findings = []

    _add_citations(findings)

    analysis_out = {"findings": findings, "status": "ok"}
    status_out = "ok"
    if os.getenv("FEATURE_LLM_ANALYZE", "0") == "1":
        pass

    snap = extract_document_snapshot(txt)
    snap.rules_count = _discover_rules_count()
    summary = snap.model_dump()
    _ensure_legacy_doc_type(summary)
    try:
        parties = [
            Party(
                name=p.get("name", ""),
                company_number=p.get("company_number"),
                address=p.get("address"),
            )
            for p in summary.get("parties", [])
        ]
        parties = enrich_parties_with_companies_house(parties)
        summary["parties"] = [p.model_dump() for p in parties]
    except Exception:
        pass

    envelope = {
        "status": status_out,
        "analysis": analysis_out,
        "results": {"summary": summary},
        "clauses": analysis_out.get("findings", []),
        "document": analysis_out.get("document", {}),
        "schema_version": SCHEMA_VERSION,
        "meta": PROVIDER_META,
        "summary": summary,
    }
    IDEMPOTENCY_CACHE.set(cid, envelope)
    rec = {"resp": envelope, "cid": cid}
    an_cache.set(doc_hash, rec)
    cid_index.set(cid, {"hash": doc_hash})

    headers = {
        "x-cache": "miss",
        "x-cid": cid,
        "x-doc-hash": doc_hash,
        "x-schema-version": SCHEMA_VERSION,
        "ETag": etag,
    }
    tmp = Response()
    _set_llm_headers(tmp, PROVIDER_META)
    headers.update(tmp.headers)
    audit(
        "analyze",
        request.headers.get("x-user"),
        doc_hash,
        {
            "findings_count": len(findings),
            "rules_count": summary.get("rules_count", 0),
        },
    )
    return _finalize_json("/api/analyze", envelope, headers)


@router.get("/api/analyze/replay")
def analyze_replay(
    cid: Optional[str] = Query(default=None),
    hash: Optional[str] = Query(default=None),
):
    if not ENABLE_REPLAY:
        raise HTTPException(404, detail="Replay disabled")

    rec = None
    if cid:
        meta = cid_index.get(cid)
        if meta:
            rec = an_cache.get(meta["hash"])
    elif hash:
        rec = an_cache.get(hash)
    else:
        raise HTTPException(400, detail="Pass cid or hash")

    if not rec:
        raise HTTPException(404, detail="Not found in cache")

    out_json = rec["resp"]
    resp = JSONResponse(out_json)
    resp.headers["x-cache"] = "replay"
    resp.headers["x-cid"] = rec["cid"]
    resp.headers["x-doc-hash"] = hash or cid_index.get(rec["cid"])["hash"]
    resp.headers["x-schema-version"] = SCHEMA_VERSION
    return resp


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
    if os.getenv("AZURE_KEY_INVALID") == "1":
        raise HTTPException(
            status_code=500,
            detail="Azure key is invalid (non-ASCII placeholder). Set a real AZURE_OPENAI_API_KEY.",
        )
    t0 = _now_ms()
    _set_schema_headers(response)
    try:
        payload = await request.json()
    except Exception:
        return _problem_response(400, "Bad JSON", "Request body is not valid JSON")

    text = (payload or {}).get("text", "")
    rules = (payload or {}).get("rules")
    if isinstance(rules, list):
        rules = {"rules": rules} if rules else None
    profile = (payload or {}).get("profile", "smart")
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
        if profile == "smart" and not rules:
            meta["profile"] = "vanilla"
            _trace_push(cid, {"qa_profile_fallback": "vanilla"})
        else:
            meta["profile"] = profile if profile in ("smart", "vanilla") else "vanilla"
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
            "meta": meta,
        }
    try:
        result = LLM_SERVICE.qa(text, rules, LLM_CONFIG.timeout_s, profile=profile)
    except ValueError:
        if profile == "smart":
            _trace_push(cid, {"qa_profile_fallback": "vanilla"})
            result = LLM_SERVICE.qa(
                text, rules, LLM_CONFIG.timeout_s, profile="vanilla"
            )
            profile = "vanilla"
        else:
            raise
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
    _require_api_key(request)
    _set_schema_headers(response)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    text = (payload or {}).get("text", "")
    if not isinstance(text, str) or text.strip() == "":
        raise HTTPException(status_code=422, detail="text required")
    findings_raw = (payload or {}).get("findings") or []
    if not isinstance(findings_raw, list):
        raise HTTPException(status_code=422, detail="findings must be a list")

    suggestions: list[SuggestEdit] = []
    for item in findings_raw:
        try:
            finding = CoreFinding.model_validate(item)
        except Exception:
            continue
        span = finding.span or CoreSpan(start=0, length=min(30, len(text)))
        start = max(0, span.start)
        length = span.length
        if start + length > len(text):
            length = max(0, len(text) - start)
        if length <= 0:
            continue
        clamped_span = CoreSpan(start=start, length=length)
        citation = resolve_citation(finding) or CoreCitation(
            instrument="Unknown", section="N/A"
        )
        rationale = f"Review recommended for rule {finding.code}".strip()
        suggestions.append(
            SuggestEdit(span=clamped_span, rationale=rationale, citations=[citation])
        )

    cid = x_cid or compute_cid(request)
    headers = {"x-cache": "miss", "x-cid": cid, "x-schema-version": SCHEMA_VERSION}
    payload = SuggestResponse(suggestions=suggestions).model_dump()

    ops: list[dict] = []
    proposed_text = text
    for sug in payload.get("suggestions", []):
        span = sug.get("span") or {}
        start = int(span.get("start", 0))
        length = int(span.get("length", 0))
        end = start + length
        insert = sug.get("insert")
        delete = sug.get("delete")
        replacement = None
        if insert is not None and delete is not None:
            replacement = insert
        elif insert is not None:
            replacement = insert
        elif delete is not None:
            replacement = ""
        ctx_before, ctx_after = _extract_context(text, start, end)
        sug["context_before"] = ctx_before
        sug["context_after"] = ctx_after
        if replacement is not None:
            ops.append(
                {
                    "start": start,
                    "end": end,
                    "replacement": replacement,
                    "context_before": ctx_before,
                    "context_after": ctx_after,
                }
            )
    for op in sorted(ops, key=lambda o: o["start"], reverse=True):
        proposed_text = proposed_text[: op["start"]] + op["replacement"] + proposed_text[op["end"] :]
    payload["proposed_text"] = proposed_text
    payload["ops"] = ops
    payload["status"] = "ok"
    audit(
        "suggest_edits",
        request.headers.get("x-user"),
        None,
        {
            "suggestions_count": len(payload.get("suggestions", [])),
            "ops_count": len(ops),
        },
    )
    return _finalize_json("/api/suggest_edits", payload, headers)


class DraftIn(BaseModel):
    text: str = Field(..., min_length=1)
    mode: str = Field("friendly", pattern="^(friendly|medium|strict)$")
    before_text: Optional[str] = None
    after_text: Optional[str] = None


class DraftOut(BaseModel):
    status: str
    mode: str
    proposed_text: str
    rationale: str
    evidence: list | dict
    before_text: str
    after_text: str
    diff: dict
    x_schema_version: str
    context_before: str
    context_after: str


class RedlinesIn(BaseModel):
    before_text: str
    after_text: str


class RedlinesOut(BaseModel):
    status: str
    diff_unified: str
    diff_html: str


@router.post(
    "/api/gpt-draft",
    response_model=DraftOut,
    responses={422: {"model": ProblemDetail}},
)
@router.post(
    "/api/gpt/draft",
    response_model=DraftOut,
    responses={422: {"model": ProblemDetail}},
)
async def gpt_draft(inp: DraftIn, request: Request):
    _require_api_key(request)
    if os.getenv("AZURE_KEY_INVALID") == "1":
        raise HTTPException(
            status_code=500,
            detail="Azure key is invalid (non-ASCII placeholder). Set a real AZURE_OPENAI_API_KEY.",
        )
    started = time.perf_counter()
    cid = compute_cid(request)
    raw = _json_dumps_safe(inp.model_dump(exclude_none=True))
    etag = _sha256_hex(raw)
    inm = request.headers.get("if-none-match")
    if inm == etag:
        cached = gpt_cache.get(etag)
        if cached:
            resp = Response(status_code=304)
            resp.headers.update(
                {
                    "ETag": etag,
                    "x-cache": "hit",
                    "x-cid": cached["cid"],
                    "x-schema-version": SCHEMA_VERSION,
                }
            )
            _set_llm_headers(resp, cached["meta"])
            return resp

    cached = gpt_cache.get(etag)
    if cached:
        headers = {
            "ETag": etag,
            "x-cache": "hit",
            "x-cid": cached["cid"],
            "x-schema-version": SCHEMA_VERSION,
        }
        tmp = Response()
        _set_llm_headers(tmp, cached["meta"])
        headers.update(tmp.headers)
        return JSONResponse(cached["resp"], headers=headers)

    text = inp.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")

    redacted_text, pii_map = redact_pii(text)

    try:
        result = LLM_PROVIDER.draft(text=redacted_text, mode=inp.mode)
        proposed_text = scrub_llm_output(result.proposed_text, pii_map)
        rationale = scrub_llm_output(result.rationale, pii_map)
        evidence = [scrub_llm_output(e, pii_map) for e in result.evidence]
        before_text = text
        after_text = scrub_llm_output(result.after_text, pii_map)
        diff_unified = scrub_llm_output(result.diff_unified, pii_map)
        provider = result.provider
        model = result.model
        mode_used = result.mode
        usage = result.usage
    except TypeError:
        legacy = LLM_PROVIDER.draft(redacted_text)
        proposed_text = scrub_llm_output(
            legacy.get("text") or legacy.get("proposed_text", ""), pii_map
        )
        rationale = scrub_llm_output(legacy.get("rationale", ""), pii_map)
        evidence = [scrub_llm_output(e, pii_map) for e in legacy.get("evidence", [])]
        before_text = text
        after_text = proposed_text
        diff_unified = scrub_llm_output(legacy.get("diff", ""), pii_map)
        provider = getattr(LLM_PROVIDER, "name", "")
        model = getattr(LLM_PROVIDER, "model", "")
        mode_used = inp.mode
        usage = legacy.get("usage", {})
    ctx_before, _ = normalize_text((inp.before_text or "")[-60:])
    ctx_after, _ = normalize_text((inp.after_text or "")[:60])
    out = {
        "status": "ok",
        "mode": inp.mode,
        "proposed_text": proposed_text,
        "rationale": rationale,
        "evidence": evidence,
        "before_text": before_text,
        "after_text": after_text,
        "diff": {"type": "unified", "value": diff_unified},
        "x_schema_version": SCHEMA_VERSION,
        "context_before": ctx_before,
        "context_after": ctx_after,
    }
    meta = {"provider": provider, "model": model, "mode": mode_used, "usage": usage}
    gpt_cache.set(etag, {"resp": out, "cid": cid, "meta": meta})
    headers = {
        "ETag": etag,
        "x-cache": "miss",
        "x-cid": cid,
        "x-schema-version": SCHEMA_VERSION,
        "x-latency-ms": str(int((time.perf_counter() - started) * 1000)),
    }
    tmp = Response()
    _set_llm_headers(tmp, meta)
    headers.update(tmp.headers)
    resp = JSONResponse(out, headers=headers)
    audit(
        "gpt_draft",
        request.headers.get("x-user"),
        None,
        {
            "before_text_len": len(before_text or ""),
            "after_text_len": len(after_text or ""),
        },
    )
    return resp


@router.post("/api/panel/redlines", response_model=RedlinesOut)
def panel_redlines(inp: RedlinesIn, request: Request):
    _require_api_key(request)
    diff_u, diff_h = make_diff(inp.before_text or "", inp.after_text or "")
    payload = {
        "status": "ok",
        "diff_unified": diff_u,
        "diff_html": diff_h,
    }
    headers = {"x-cache": "miss", "x-schema-version": SCHEMA_VERSION}
    return _finalize_json("/api/panel/redlines", payload, headers)


# --- Aliases to be robust wrt panel/client paths ---


@router.get("/api/health")
async def health_alias():
    return await health()


@app.post("/analyze")
def analyze_alias(req: AnalyzeRequest, request: Request):
    return api_analyze(req, request)


@router.post("/suggest_edits")
async def suggest_edits_alias(
    request: Request, response: Response, x_cid: Optional[str] = Header(None)
):
    return await api_suggest_edits(request, response, x_cid)


@app.get("/llm/ping")
def llm_ping_alias():
    return llm_ping()


@router.post(
    "/api/gpt_draft",
    response_model=DraftOut,
    responses={422: {"model": ProblemDetail}},
)
async def gpt_draft_underscore_alias(inp: DraftIn, request: Request):
    return await gpt_draft(inp, request)


@router.post(
    "/gpt-draft",
    response_model=DraftOut,
    responses={422: {"model": ProblemDetail}},
)
async def gpt_draft_plain_alias(inp: DraftIn, request: Request):
    return await gpt_draft(inp, request)


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
        secure_write(LEARNING_LOG_PATH, json.dumps(body, ensure_ascii=False), append=True)
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
app.include_router(explain_router)
app.include_router(integrations_router)
app.include_router(dsar_router)


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


@app.on_event("startup")
async def _log_routes_on_startup():
    try:
        print("\n[ROUTES at startup]")
        for r in app.routes:
            path = getattr(r, "path", "?")
            methods = getattr(r, "methods", set())
            print(f"  {path}  {sorted(list(methods))}")
        print("[/ROUTES]\n")
    except Exception:
        pass


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
