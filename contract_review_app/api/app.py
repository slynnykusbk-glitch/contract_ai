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
from html import escape as html_escape
import time
from datetime import datetime, timezone
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from collections import OrderedDict
import secrets
from starlette.middleware.base import BaseHTTPMiddleware
import mimetypes

try:  # Starlette <0.37 compatibility
    from starlette.middleware.timeout import TimeoutMiddleware
except Exception:  # pragma: no cover

    class TimeoutMiddleware:  # type: ignore
        def __init__(self, app, timeout=60):
            self.app = app
            self.timeout = timeout

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)


from contract_review_app.core.privacy import redact_pii, scrub_llm_output  # noqa: F401
from contract_review_app.core.audit import audit
from contract_review_app.security.secure_store import secure_write
from contract_review_app.core.trace import TraceStore, compute_cid
from contract_review_app.core.lx_types import LxFeatureSet, LxSegment
from contract_review_app.config import CH_ENABLED, CH_API_KEY
from contract_review_app.utils.logging import logger as cai_logger
from contract_review_app.legal_rules import constraints
from contract_review_app.legal_rules.aggregate import apply_merge_policy
from contract_review_app.legal_rules.constraints import InternalFinding
from contract_review_app.trace_artifacts import (
    build_constraints,
    build_dispatch,
    build_features,
    build_proposals,
)


log = logging.getLogger("contract_ai")

# prevent serving TypeScript files with executable MIME types
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/plain", ".ts")

# корень репо: .../contract_ai
REPO_DIR = Path(__file__).resolve().parents[2]
PANEL_DIR = (
    REPO_DIR / "contract_review_app" / "contract_review_app" / "static" / "panel"
)
PANEL_ASSETS_DIR = PANEL_DIR / "app" / "assets"


def _resolve_catalog_dir() -> Path:
    """Resolve the shared catalog directory used for the sideload manifest."""

    user_candidates: list[Path] = []

    raw_user = os.getenv("USERPROFILE")
    if raw_user:
        user_candidates.append(Path(os.path.expandvars(raw_user)))

    home_drive = os.getenv("HOMEDRIVE")
    home_path = os.getenv("HOMEPATH")
    if home_drive and home_path:
        user_candidates.append(Path(home_drive) / home_path.lstrip("\\/"))

    user_candidates.append(Path.home())

    catalog_candidates: list[Path] = []
    seen: set[Path] = set()

    for base in user_candidates:
        candidate = base / "contract_ai" / "_shared_catalog"
        if candidate not in seen:
            catalog_candidates.append(candidate)
            seen.add(candidate)

    repo_fallback = REPO_DIR / "_shared_catalog"
    if repo_fallback not in seen:
        catalog_candidates.append(repo_fallback)
        seen.add(repo_fallback)

    for candidate in catalog_candidates:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue

    return catalog_candidates[0]


CATALOG_DIR = _resolve_catalog_dir()

log.info("[PANEL] mount /panel -> %s", PANEL_DIR.resolve())
token_path = PANEL_DIR / ".build-token"
taskpane_bundle = PANEL_DIR / "taskpane.bundle.js"
office_js = PANEL_ASSETS_DIR / "office.js"

token_exists = token_path.is_file()
files_exist = taskpane_bundle.is_file() and office_js.is_file()
PANEL_READY = token_exists or files_exist
if not PANEL_READY:
    log.warning(
        "[PANEL] missing build artifacts – run `npm run build` before starting the backend"
    )

try:
    PANEL_BUILD_TOKEN = token_path.read_text(encoding="utf-8").strip()
except OSError:
    PANEL_BUILD_TOKEN = "absent"
log.info("[PANEL] build token: %s", PANEL_BUILD_TOKEN)


TRACE_MAX = int(os.getenv("TRACE_MAX", "200"))


TRACE = TraceStore(TRACE_MAX)

# flag indicating whether rule engine is usable
_RULE_ENGINE_OK = True
_RULE_ENGINE_ERR = ""

# Stable CID used when clients do not supply one
_PROCESS_CID = str(uuid.uuid4())


class NormalizeAndTraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "HEAD" and request.url.path.startswith("/panel/"):
            return await call_next(request)

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
            headers["x-cid"] = cid

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = body.decode("utf-8", "replace")

        classifiers: Dict[str, Any] = {}
        if isinstance(payload, dict):
            summary = (
                payload.get("summary")
                or (payload.get("results") or {}).get("summary")
                or {}
            )
            doc_type = summary.get("type")
            confidence = summary.get("type_confidence")
            language = summary.get("language")

            clause_types: set[str] = set()
            analyses = []
            if isinstance(payload.get("document"), dict):
                analyses = payload.get("document", {}).get("analyses", []) or []
            if not analyses and isinstance(payload.get("analyses"), list):
                analyses = payload.get("analyses") or []
            for a in analyses:
                ct = a.get("clause_type") if isinstance(a, dict) else None
                if ct:
                    clause_types.add(str(ct))
            for c in payload.get("clauses", []) or []:
                ct = c.get("clause_type") if isinstance(c, dict) else None
                if ct:
                    clause_types.add(str(ct))

            try:
                from contract_review_app.legal_rules import loader as _loader  # type: ignore

                packs = [p.get("path") for p in _loader.loaded_packs()]
            except Exception:
                packs = []

            classifiers = {
                "document_type": doc_type,
                "confidence": confidence,
                "clause_types": sorted(clause_types),
                "active_rule_packs": packs,
                "language": language,
            }

        TRACE.put(
            cid,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path,
                "status": response.status_code,
                "headers": dict(new_resp.headers),
                "body": payload,
                **({"classifiers": classifiers} if classifiers else {}),
            },
        )
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
    rule_count = 0
    try:
        rule_count = int(payload.get("meta", {}).get("rules_evaluated", 0))
    except Exception:
        rule_count = 0
    hdrs["x-rule-count"] = str(rule_count)
    return JSONResponse(payload, status_code=status_code, headers=hdrs)


def _validate_env_vars() -> None:
    key = (os.getenv("AZURE_OPENAI_API_KEY", "") or "").strip()
    invalid = False
    if not key or key in {"*", "changeme"} or len(key) < 24:
        invalid = True
    # если ключ указан, он должен быть чистым ASCII
    if key and any(ord(ch) > 127 for ch in key):
        invalid = True
    if invalid:
        msg = (
            "AZURE_OPENAI_API_KEY is missing or looks like a placeholder. "
            "Set a real Azure key."
        )
        log.error(msg)
        os.environ["AZURE_KEY_INVALID"] = "1"

    # ensure PyYAML and rule packs are available
    global _RULE_ENGINE_OK, _RULE_ENGINE_ERR
    try:
        import yaml  # type: ignore  # noqa: F401
        from contract_review_app.legal_rules import loader as _loader

        _loader.load_rule_packs()
        if _loader.rules_count() <= 0:
            raise RuntimeError("no rule packs loaded")
    except Exception as exc:  # pragma: no cover - best effort only
        log.warning("Rule engine unavailable: %s", exc)
        _RULE_ENGINE_OK = False
        _RULE_ENGINE_ERR = str(exc)


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
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)
from fastapi.openapi.utils import get_openapi
from .error_handlers import register_error_handlers
from .headers import apply_std_headers
from .mw_utils import capture_response, normalize_status_if_json
from .models import (
    CitationInput,
    CitationResolveRequest,
    CitationResolveResponse,
    CorpusSearchRequest,  # noqa: F401
    CorpusSearchResponse,  # noqa: F401
    ProblemDetail,
    QARecheckIn,
    QARecheckOut,
    SummaryIn,
    Finding,
    Span,
    Segment,
    SearchHit,
    DraftRequest,
    DraftResponse,
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
from contract_review_app.intake.normalization import (
    normalize_text,
    normalize_for_intake,
)

# --- LLM provider & limits (final resolution) ---
from contract_review_app.llm.provider import get_provider
from contract_review_app.api.limits import API_TIMEOUT_S, API_RATE_LIMIT_PER_MIN

from .middlewares import RequireHeadersMiddleware


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
from contract_review_app.integrations.service import (
    enrich_parties_with_companies_house,
    build_companies_meta,
)
from contract_review_app.core.schemas import Party
from contract_review_app.api.calloff_validator import validate_calloff
from contract_review_app.analysis import (
    parser as analysis_parser,
    classifier as analysis_classifier,
)
from contract_review_app.intake.parser import ParsedDocument
from contract_review_app.legal_rules import runner as legal_runner

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
MODEL_DRAFT = LLM_CONFIG.model_draft
MODEL_SUGGEST = LLM_CONFIG.model_suggest
MODEL_QA = LLM_CONFIG.model_qa


def _analyze_document(text: str, risk: str = "medium") -> Dict[str, Any] | JSONResponse:
    """Analyze ``text`` using the lightweight rule engine.

    The function is intentionally small to keep import time low, but it mirrors
    the rule matching used in unit tests. Tests may monkeypatch this function
    to provide custom behaviour.
    """
    try:
        from contract_review_app.legal_rules import loader, engine
    except ImportError:
        log.exception("YAML rule engine import failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_code": "rule_engine_unavailable",
                "detail": "YAML rule engine is unavailable",
            },
        )

    findings = engine.analyze(text or "", loader._RULES)
    for f in findings:
        snip = f.get("snippet")
        if isinstance(snip, str):
            f["normalized_snippet"] = normalize_for_intake(snip)

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
    src = summary.get("type_source")
    if src:
        summary["doc_type"]["source"] = src


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
_default_responses = {code: _default_problem for code in (400, 401, 403, 404, 429, 500)}
app = FastAPI(
    title="Contract Review App API",
    version="1.0",
    lifespan=lifespan,
    responses=_default_responses,
)
register_error_handlers(app)

# --- begin minimal patch for /catalog ---
from pathlib import Path
from fastapi.staticfiles import StaticFiles


def _resolve_catalog_dir() -> Path:
    """
    Robust resolver for the catalog folder used by Word shared catalog.
    Creates the folder if missing and returns its path.
    Tries repo-root\_shared_catalog first; falls back to %USERPROFILE%\contract_ai\_shared_catalog.
    """

    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "_shared_catalog",  # <repo>\_shared_catalog
        Path.home() / "contract_ai" / "_shared_catalog",  # %USERPROFILE%\contract_ai\_shared_catalog
    ]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    # last resort: use a folder next to this file
    fallback = here.parent / "_shared_catalog"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


CATALOG_DIR = _resolve_catalog_dir()
_CATALOG_MOUNTED = False
try:
    app.mount("/catalog", StaticFiles(directory=str(CATALOG_DIR)), name="catalog")
    print(f"[catalog] mounted at /catalog -> {CATALOG_DIR}")
    _CATALOG_MOUNTED = True
except Exception as e:
    print(f"[catalog] failed to mount: {e}")
# --- end minimal patch ---

# ---------------------------- Panel sub-app ----------------------------
if PANEL_READY:
    panel_app = FastAPI()

    @panel_app.middleware("http")
    async def _panel_no_cache(request: Request, call_next):
        resp = await call_next(request)
        path = request.url.path
        if path.endswith("taskpane.bundle.js"):
            resp.headers["Cache-Control"] = "no-cache"
        else:
            resp.headers["Cache-Control"] = "no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @panel_app.get("/version.json")
    async def panel_version() -> dict:
        return {"version": app.version, "schema_version": SCHEMA_VERSION}

    @panel_app.head("/{path:path}")
    async def panel_head(path: str = ""):
        base = PANEL_DIR.resolve()
        full = (base / path).resolve()
        if full.is_dir():
            full = full / "index.html"
        try:
            full.relative_to(base)
        except ValueError:
            raise HTTPException(status_code=404)
        if not full.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(full)

    panel_app.mount(
        "/app/assets",
        StaticFiles(directory=str(PANEL_ASSETS_DIR), html=False),
        name="assets",
    )
    panel_app.mount("/", StaticFiles(directory=str(PANEL_DIR), html=True), name="root")
else:

    async def panel_app(scope, receive, send):  # type: ignore[override]
        await Response(status_code=404)(scope, receive, send)


app.mount("/panel", panel_app, name="panel")

# Локальный каталог с манифестом
if CATALOG_DIR.is_dir() and not _CATALOG_MOUNTED:
    log.info("[CATALOG] mount /catalog -> %s", CATALOG_DIR.resolve())
    app.mount("/catalog", StaticFiles(directory=str(CATALOG_DIR)), name="catalog")

# instantiate LLM provider once
PROVIDER = get_provider()
LLM_PROVIDER = PROVIDER


def _extract_region(endpoint: str) -> str:
    try:
        host = endpoint.split("//", 1)[1]
        return host.split(".")[0]
    except Exception:
        return ""


PROVIDER_META = {
    "provider": LLM_CONFIG.provider,
    "model": MODEL_DRAFT,
}
if LLM_CONFIG.provider == "azure":
    ep = (LLM_CONFIG.azure_endpoint or "").rstrip("/")
    dep = LLM_CONFIG.azure_deployment or MODEL_DRAFT
    PROVIDER_META.update(
        {
            "endpoint": ep,
            "deployment": dep,
            "api_version": LLM_CONFIG.azure_api_version or "",
            "region": _extract_region(ep) if ep else "",
        }
    )
# In mock mode we ignore any Azure key validation flags
PROVIDER_META["valid_config"] = LLM_CONFIG.valid and (
    LLM_CONFIG.mode == "mock" or os.getenv("AZURE_KEY_INVALID") != "1"
)
if "endpoint" in PROVIDER_META:
    PROVIDER_META["ep"] = PROVIDER_META["endpoint"][:2]
if "deployment" in PROVIDER_META:
    PROVIDER_META["dep"] = PROVIDER_META["deployment"][:2]

ANALYZE_CACHE_TTL_S = int(os.getenv("ANALYZE_CACHE_TTL_S", "900"))
ANALYZE_CACHE_MAX = int(os.getenv("ANALYZE_CACHE_MAX", "128"))
ENABLE_REPLAY = os.getenv("ANALYZE_REPLAY_ENABLED", "1") == "1"


def _llm_key_problem() -> ProblemDetail:
    return ProblemDetail(
        title="Invalid LLM key",
        status=400,
        code="invalid_llm_key",
        detail="AZURE_OPENAI_API_KEY is missing or invalid",
        extra={"meta": PROVIDER_META},
    )


def _ensure_llm_ready() -> None:
    if LLM_CONFIG.provider == "azure" and not PROVIDER_META.get("valid_config"):
        problem = _llm_key_problem()
        raise HTTPException(status_code=400, detail=problem.model_dump())


an_cache = TTLCache(max_items=ANALYZE_CACHE_MAX, ttl_s=ANALYZE_CACHE_TTL_S)
cid_index = TTLCache(max_items=ANALYZE_CACHE_MAX, ttl_s=ANALYZE_CACHE_TTL_S)
gpt_cache = TTLCache(max_items=ANALYZE_CACHE_MAX, ttl_s=ANALYZE_CACHE_TTL_S)

FEATURE_METRICS = os.getenv("FEATURE_METRICS", "1") == "1"
FEATURE_LX_ENGINE = os.getenv("FEATURE_LX_ENGINE", "0") == "1"
FEATURE_TRACE_ARTIFACTS = os.getenv("FEATURE_TRACE_ARTIFACTS", "0") == "1"
LX_L2_CONSTRAINTS = os.getenv("LX_L2_CONSTRAINTS", "0") == "1"
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
        _ensure_llm_ready()
    except HTTPException as exc:
        return JSONResponse(exc.detail, status_code=exc.status_code)
    try:
        res = PROVIDER.ping()
        return {
            "status": "ok",
            "latency_ms": res.get("latency_ms", 0),
            "meta": PROVIDER_META,
        }
    except Exception as e:
        problem = ProblemDetail(
            title="LLM ping failed",
            status=502,
            detail=str(e),
            extra={"meta": PROVIDER_META},
        )
        return JSONResponse(problem.model_dump(), status_code=502)


class AnalyzeRequest(BaseModel):
    """Public request DTO for ``/api/analyze``.

    Accepts ``text`` as a required field while allowing legacy aliases
    ``clause`` and ``body`` for backward compatibility. The aliases are
    folded into ``text`` during validation so downstream logic only needs to
    handle a single attribute.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra={"example": {"text": "Hello", "language": "en-GB"}},
    )

    text: str = Field(
        validation_alias=AliasChoices("text", "clause", "body"),
        min_length=1,
    )
    language: str = "en-GB"
    mode: Optional[str] = None
    risk: Optional[str] = None
    clause_type: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")

    @field_validator("text")
    @classmethod
    def _strip_text(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("text is empty")
        return v

    @field_validator("language", mode="before")
    @classmethod
    def _default_language(cls, v: str | None) -> str:
        """Normalize language, falling back to the default."""
        if not v or not str(v).strip():
            return "en-GB"
        return str(v)

    @field_validator("mode", "risk", mode="before")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        """Treat empty strings as missing values."""
        if isinstance(v, str) and not v.strip():
            return None
        return v


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
    schemas["DraftRequest"] = DraftRequest.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    for _m in [Finding, Span, Segment, SearchHit, CitationInput]:
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

    for p in ["/api/analyze", "/api/gpt-draft", "/api/explain"]:
        op = openapi_schema.get("paths", {}).get(p, {}).get("post")
        if not op:
            continue
        resp = op.get("responses", {}).get("200", {})
        content = resp.setdefault("content", {}).setdefault("application/json", {})
        content.setdefault("examples", {})["default"] = {
            "summary": "Example",
            "value": {},
        }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = _custom_openapi

_TRUTHY = {"1", "true", "yes", "on", "enabled"}


def _env_truthy(name: str) -> bool:
    """Return ``True`` if environment variable ``name`` is set to a truthy value."""
    return (os.getenv(name, "") or "").strip().lower() in _TRUTHY


_ALLOWED_ORIGINS = [
    o.strip()
    for o in (os.getenv("ALLOWED_ORIGINS") or "https://127.0.0.1:9443").split(",")
    if o.strip()
]


def require_llm_enabled() -> None:
    if not _env_truthy("CONTRACTAI_LLM_API"):
        raise HTTPException(status_code=404, detail="LLM API disabled")


# Optional legacy LLM API removed

# Middleware stack: CORS -> Error -> Timeout -> Trace -> RequireHeaders -> Router
app.add_middleware(RequireHeadersMiddleware)
app.add_middleware(NormalizeAndTraceMiddleware)
app.add_middleware(
    TimeoutMiddleware,
    timeout=float(os.getenv("REQUEST_TIMEOUT_S", "60")),
)
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


# log request details at INFO level
@app.middleware("http")
async def _request_logger(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        ms = (time.perf_counter() - start) * 1000
        cai_logger.info(
            "{method} {path} -> {status} ({ms:.2f} ms)",
            method=request.method,
            path=request.url.path,
            status=500,
            ms=ms,
        )
        raise
    ms = (time.perf_counter() - start) * 1000
    cai_logger.info(
        "{method} {path} -> {status} ({ms:.2f} ms)",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=ms,
    )
    return response


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
    try:
        body = await _read_body_guarded(request)
    except HTTPException:
        cid = getattr(
            request.state, "cid", request.headers.get("x-cid") or _PROCESS_CID
        )
        return _problem_response(
            413,
            "Payload too large",
            error_code="payload_too_large",
            detail="Request body exceeds limits",
            cid=cid,
        )
    started_at = time.perf_counter()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(request.scope, receive)
    request.state.body = body
    request.state.started_at = started_at
    if request.method.upper() in {"POST", "PUT", "PATCH"} and body:
        try:
            request.state.json = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            cid = getattr(
                request.state, "cid", request.headers.get("x-cid") or _PROCESS_CID
            )
            return _problem_response(
                400,
                "Bad JSON",
                error_code="bad_json",
                detail="Request body is not valid JSON",
                cid=cid,
            )
    response = await call_next(request)
    if "x-schema-version" not in response.headers:
        apply_std_headers(response, request, started_at)
    return response


@app.middleware("http")
async def _trace_mw(request: Request, call_next):
    t0 = time.perf_counter()
    req_cid = getattr(
        request.state, "cid", request.headers.get("x-cid") or _PROCESS_CID
    )
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
    response.headers["x-schema-version"] = SCHEMA_VERSION


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
    status: int,
    title: str,
    detail: str | None = None,
    error_code: str | None = None,
    type_: str = "/errors/general",
) -> Dict[str, Any]:
    data = ProblemDetail(
        status=status, title=title, detail=detail, type=type_, code=error_code
    ).model_dump()
    if error_code:
        data["error_code"] = error_code
    return data


def _problem_response(
    status: int,
    title: str,
    error_code: str | None = None,
    detail: str | None = None,
    cid: str | None = None,
) -> JSONResponse:
    resp = JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=_problem_json(status, title, detail, error_code),
    )
    if cid:
        resp.headers["x-cid"] = cid
    resp.headers["x-schema-version"] = SCHEMA_VERSION
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
        if "findings" in payload:
            findings = payload["findings"]
        elif (
            isinstance(payload.get("results"), dict)
            and "findings" in payload["results"]
        ):
            findings = payload["results"]["findings"]
        elif (
            isinstance(payload.get("results"), dict)
            and isinstance(payload["results"].get("analysis"), dict)
            and "findings" in payload["results"]["analysis"]
        ):
            findings = payload["results"]["analysis"]["findings"]
    out.setdefault("results", {})
    out["results"].setdefault("analysis", {})
    out["results"]["analysis"]["findings"] = findings
    out["status"] = out.get("status", "OK").upper() or "OK"
    return out


async def _read_body_guarded(request: Request) -> bytes:
    body = await request.body()
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
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


def _extract_context(
    text: str, start: int, end: int, width: int = 60
) -> tuple[str, str]:
    """Return normalized context strings around the given span."""
    before_raw = text[max(0, start - width) : start]
    after_raw = text[end : end + width]
    before_norm, _ = normalize_text(before_raw)
    after_norm, _ = normalize_text(after_raw)
    return before_norm, after_norm


RULE_DISCOVERY_TIMEOUT_S = float(os.getenv("RULE_DISCOVERY_TIMEOUT_S", "1.5"))


async def _discover_rules_count() -> int:
    async def _inner() -> int:
        try:
            if rules_loader and hasattr(rules_loader, "rules_count"):
                return int(await _maybe_await(rules_loader.rules_count))
        except Exception:
            pass
        try:
            if rules_registry and hasattr(rules_registry, "discover_rules"):
                rules = await _maybe_await(rules_registry.discover_rules)
                return len(rules or [])
        except Exception:
            pass
        return 0

    try:
        return await asyncio.wait_for(_inner(), timeout=RULE_DISCOVERY_TIMEOUT_S)
    except asyncio.TimeoutError:
        global _RULE_ENGINE_OK, _RULE_ENGINE_ERR
        _RULE_ENGINE_OK = False
        _RULE_ENGINE_ERR = "timeout"
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
    global _RULE_ENGINE_OK, _RULE_ENGINE_ERR
    rules_count = await _discover_rules_count()
    payload = {
        "status": "ok",
        "schema": SCHEMA_VERSION,
        "rules_count": rules_count,
        "llm": {
            "provider": LLM_CONFIG.provider,
            "models": {
                "draft": MODEL_DRAFT,
                "suggest": MODEL_SUGGEST,
                "qa": MODEL_QA,
            },
            "mode": LLM_CONFIG.mode,
            "timeout_s": LLM_CONFIG.timeout_s,
        },
        "provider": PROVIDER_META,
        "ch": {"enabled": CH_ENABLED, "keylen": len(CH_API_KEY or "")},
        "endpoints": ["/api/analyze", "/api/gpt-draft", "/api/explain"],
    }
    status_code = 200
    if not _RULE_ENGINE_OK:
        payload["status"] = "error"
        payload.setdefault("meta", {})["rule_engine"] = (
            _RULE_ENGINE_ERR or "unavailable"
        )
        status_code = 500
    if _RULE_ENGINE_OK:
        try:
            if rules_loader and hasattr(rules_loader, "loaded_packs"):
                packs = await asyncio.wait_for(
                    _maybe_await(rules_loader.loaded_packs),
                    timeout=RULE_DISCOVERY_TIMEOUT_S,
                )
                for pack in packs:
                    p = pack.get("path")
                    if p:
                        pack["path"] = PurePosixPath(Path(p)).as_posix()
                payload.setdefault("meta", {})["rules"] = packs
        except asyncio.TimeoutError:
            _RULE_ENGINE_OK = False
            _RULE_ENGINE_ERR = "timeout"
            payload.setdefault("meta", {})["rules"] = []
            payload.setdefault("meta", {})["rule_engine"] = "timeout"
            status_code = 500
        except Exception:
            payload.setdefault("meta", {})["rules"] = []
    else:
        payload.setdefault("meta", {})["rules"] = []
    headers = {"x-schema-version": SCHEMA_VERSION}
    return _finalize_json("/health", payload, headers, status_code=status_code)


@router.get("/api/supports")
async def api_supports() -> JSONResponse:
    payload = {"status": "ok", "supports": {"comments": True, "content_controls": True}}
    headers = {"x-schema-version": SCHEMA_VERSION}
    return _finalize_json("/api/supports", payload, headers)


@router.get("/api/trace")
async def list_trace():
    return {"cids": TRACE.list()[-50:]}


@router.get("/api/trace/{cid}.html")
async def get_trace_html(cid: str):
    if not _CID_RE.fullmatch(cid or ""):
        resp = _problem_response(
            404,
            "trace not found",
            error_code="trace_not_found",
            detail="trace not found",
            cid=cid,
        )
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    trace = TRACE.get(cid)
    if not trace:
        resp = _problem_response(
            404,
            "trace not found",
            error_code="trace_not_found",
            detail="trace not found",
            cid=cid,
        )
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    html = "<pre>" + html_escape(json.dumps(trace, indent=2)) + "</pre>"
    resp = Response(content=html, media_type="text/html; charset=utf-8")
    _set_schema_headers(resp)
    _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
    resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


@router.get("/api/trace/{cid}")
async def get_trace(cid: str):
    if not _CID_RE.fullmatch(cid or ""):
        raise HTTPException(status_code=404, detail="trace not found")
    trace = TRACE.get(cid)
    if not trace:
        raise HTTPException(status_code=404, detail="trace not found")
    body = dict(trace.get("body") or {})
    body["cid"] = cid
    body["created_at"] = trace.get("ts")
    return body


@router.get("/api/report/{cid}.html")
async def api_report_html(cid: str):
    if not _CID_RE.fullmatch(cid or ""):
        resp = _problem_response(
            404,
            "trace not found",
            error_code="trace_not_found",
            detail="trace not found",
            cid=cid,
        )
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    trace = TRACE.get(cid)
    if not trace:
        resp = _problem_response(
            404,
            "trace not found",
            error_code="trace_not_found",
            detail="trace not found",
            cid=cid,
        )
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    html = render_html_report(trace)
    resp = Response(content=html, media_type="text/html; charset=utf-8")
    _set_schema_headers(resp)
    _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
    resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


@router.get("/api/report/{cid}.pdf")
async def api_report_pdf(cid: str):
    if not _CID_RE.fullmatch(cid or ""):
        resp = _problem_response(
            404,
            "trace not found",
            error_code="trace_not_found",
            detail="trace not found",
            cid=cid,
        )
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    trace = TRACE.get(cid)
    if not trace:
        resp = _problem_response(
            404,
            "trace not found",
            error_code="trace_not_found",
            detail="trace not found",
            cid=cid,
        )
        _set_std_headers(resp, cid=cid, xcache="miss", schema=SCHEMA_VERSION)
        return resp
    html = render_html_report(trace)
    try:
        pdf_bytes = html_to_pdf(html)
    except NotImplementedError:
        resp = _problem_response(
            501,
            "PDF export not enabled",
            error_code="pdf_export_not_enabled",
            detail="PDF export not enabled",
            cid=cid,
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
    return Response(
        csv_text, media_type="text/csv", headers={"Cache-Control": "no-store"}
    )


@router.get("/api/metrics.html")
async def api_metrics_html():
    if not FEATURE_METRICS:
        raise HTTPException(status_code=404, detail="disabled")
    resp = collect_metrics()
    html = render_metrics_html(resp)
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-store"})


@router.post("/api/admin/purge")
def api_admin_purge(dry: int = 1):
    removed = retention_purge(dry_run=bool(dry))
    return {"removed": [str(p) for p in removed]}


@app.post(
    "/api/analyze",
    response_model=AnalyzeResponse,
)
def api_analyze(request: Request, body: dict = Body(..., example={"text": "Hello"})):
    data = body
    if isinstance(body, dict):
        payload = body.get("payload")
        if isinstance(payload, dict):
            data = payload
    try:
        req = AnalyzeRequest.model_validate(data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())
    clause_type = request.query_params.get("clause_type")
    if clause_type:
        req.clause_type = clause_type
    if FEATURE_TRACE_ARTIFACTS:
        TRACE.add(request.state.cid, "features", {})
        TRACE.add(
            request.state.cid,
            "dispatch",
            build_dispatch(0, 0, 0, []),
        )
        TRACE.add(request.state.cid, "constraints", build_constraints([]))
        TRACE.add(request.state.cid, "proposals", build_proposals())
    txt = req.text
    debug = request.query_params.get("debug")  # noqa: F841
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
                }
            )
            _set_llm_headers(resp, PROVIDER_META)
            return resp

    cached = an_cache.get(doc_hash)
    if cached:
        resp_json = cached["resp"]
        resp_cid = cached["cid"]
        headers = {
            "x-cache": "hit",
            "x-cid": resp_cid,
            "x-doc-hash": doc_hash,
            "ETag": etag,
        }
        tmp = Response()
        _set_llm_headers(tmp, PROVIDER_META)
        headers.update(tmp.headers)
        return _finalize_json("/api/analyze", resp_json, headers)

    req_hash = compute_cid(request)
    cached_resp = IDEMPOTENCY_CACHE.get(req_hash)
    if cached_resp is not None:
        # map the current CID to the cached response for downstream summary calls
        IDEMPOTENCY_CACHE.set(request.state.cid, cached_resp)
        cid_index.set(request.state.cid, {"hash": doc_hash})
        headers = {
            "x-cache": "hit",
            "x-cid": request.state.cid,
            "x-doc-hash": doc_hash,
            "ETag": etag,
        }
        tmp = Response()
        _set_llm_headers(tmp, PROVIDER_META)
        headers.update(tmp.headers)
        return _finalize_json("/api/analyze", cached_resp, headers)

    # full parsing/classification/rule pipeline with timings
    pipeline_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    parsed_doc = ParsedDocument.from_text(txt)
    parsed = analysis_parser.parse_text(txt)
    doc_language = str(getattr(parsed_doc, "language", "") or "").lower()
    t1 = time.perf_counter()

    lx_features = None  # noqa: F841  # reserved for future L0 integration
    if FEATURE_LX_ENGINE:
        try:
            from contract_review_app.analysis import lx_features as _lx_features
        except ImportError:
            lx_features = None
        else:
            try:
                lx_features = _lx_features.extract_l0_features(txt, parsed.segments)
            except Exception:
                lx_features = None
            segments = getattr(parsed, "segments", None) or []
            try:
                segment_count = len(segments)
            except Exception:
                segment_count = 0
            TRACE.add(
                request.state.cid,
                "l0_features",
                {"status": "enabled", "count": segment_count},
            )
    analysis_classifier.classify_segments(parsed.segments)
    t2 = time.perf_counter()

    snap = extract_document_snapshot(txt)

    if FEATURE_TRACE_ARTIFACTS:
        hints = getattr(snap, "hints", None) if snap else []
        TRACE.add(
            request.state.cid,
            "features",
            build_features(parsed_doc, parsed.segments, hints),
        )

    seg_findings: List[Dict[str, Any]] = []
    clause_types_set: set[str] = set()
    dispatch_segments: List[Dict[str, Any]] = []
    dispatch_candidates: List[Dict[str, Any]] = []
    evaluated_rule_ids: Set[str] = set()
    triggered_rule_ids: Set[str] = set()
    active_pack_set: Set[str] = set()
    segments_for_yaml: List[Tuple[int, str, int]] = []
    candidate_rules_by_segment: Dict[int, Set[str]] = {}
    dispatcher_mod = None
    features_by_segment: Dict[int, LxFeatureSet] = {}
    if FEATURE_LX_ENGINE and lx_features is not None:
        try:
            from contract_review_app.legal_rules import dispatcher as _dispatcher_mod
        except Exception:
            dispatcher_mod = None
        else:
            dispatcher_mod = _dispatcher_mod
            features_by_segment = getattr(lx_features, "by_segment", {}) or {}

    for seg in parsed.segments:
        seg_id = int(seg.get("id", 0) or 0)
        seg_text = str(seg.get("text") or "")
        seg_start = int(seg.get("start") or 0)
        segments_for_yaml.append((seg_id, seg_text, seg_start))
        if dispatcher_mod and seg_id in features_by_segment:
            feats = features_by_segment.get(seg_id)
            if feats is not None:
                try:
                    segment_obj = LxSegment(
                        segment_id=seg_id,
                        heading=str(seg.get("heading") or "") or None,
                        text=str(seg.get("text") or ""),
                        clause_type=str(seg.get("clause_type") or "") or None,
                    )
                    refs = dispatcher_mod.select_candidate_rules(segment_obj, feats)
                except Exception:
                    refs = []
                if refs:
                    candidate_ids = [ref.rule_id for ref in refs]
                    candidate_rules_by_segment[seg_id] = set(candidate_ids)
                    if hasattr(feats, "model_dump"):
                        feat_payload = feats.model_dump()
                    else:  # pragma: no cover
                        feat_payload = feats.dict()  # type: ignore[call-arg]
                    dispatch_segments.append(
                        {
                            "segment_id": seg_id,
                            "labels": list(feats.labels or []),
                            "features": feat_payload,
                            "candidates": [
                                {
                                    "rule_id": ref.rule_id,
                                    "reasons": list(ref.reasons),
                                }
                                for ref in refs
                            ],
                        }
                    )

        clause_type = seg.get("clause_type")
        if not clause_type:
            continue
        clause_types_set.add(clause_type)

        for f in seg.get("findings", []) or []:
            f2 = dict(f)
            f2["clause_type"] = clause_type
            f2.setdefault("citations", [])
            seg_findings.append(f2)

        # execute python rule via runner (best effort)
        try:
            legal_runner.run_rule_for_clause(
                clause_type,
                seg_text,
                int(seg.get("start", 0)),
            )
        except Exception:
            pass

    jurisdiction = getattr(snap, "jurisdiction", "") or ""

    def merge_findings(
        existing: List[Dict[str, Any]], new_items: Iterable[Any]
    ) -> List[Dict[str, Any]]:
        """Merge serialized findings with L2 constraint results."""

        merged: List[Dict[str, Any]] = list(existing or [])
        seen_ids: Set[str] = set()
        for item in merged:
            rule_id = item.get("rule_id") if isinstance(item, dict) else None
            if rule_id:
                seen_ids.add(str(rule_id))

        new_payloads: List[Dict[str, Any]] = []
        for item in new_items or []:
            if isinstance(item, InternalFinding):
                try:
                    payload = json.loads(item.model_dump_json(exclude_none=True))
                except Exception:
                    payload = item.model_dump(exclude_none=True)
            else:
                continue

            rule_id = payload.get("rule_id")
            if not rule_id or str(rule_id) in seen_ids:
                continue

            anchors = payload.get("anchors") or []
            new_payloads.append(
                {
                    "rule_id": rule_id,
                    "severity": payload.get("severity"),
                    "message": payload.get("message", ""),
                    "snippet": payload.get("message", ""),
                    "advice": payload.get("message", ""),
                    "scope": {"unit": payload.get("scope", "doc")},
                    "law_refs": [],
                    "conflict_with": [],
                    "ops": [],
                    "occurrences": 1,
                    "anchors": anchors,
                    "citations": [],
                    "source": "constraints",
                }
            )
            seen_ids.add(str(rule_id))

        merged = apply_merge_policy(merged)
        if new_payloads:
            new_payloads.sort(key=lambda item: str(item.get("rule_id") or ""))
            merged.extend(new_payloads)

        return merged

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
    active_packs: List[str] = []
    rules_loaded = 0
    fired_rules_meta: List[Dict[str, Any]] = []
    coverage_rules: List[Dict[str, Any]] = []
    matched_rules: List[Dict[str, Any]] = []
    load_duration = 0.0
    run_duration = 0.0
    try:
        from contract_review_app.legal_rules import loader as yaml_loader, engine as yaml_engine

        # --- YAML rule engine integration (HF-0 + L1 merged) ---
        need_load = False
        try:
            need_load = yaml_loader.rules_count() == 0
        except Exception:
            need_load = False

        if need_load:
            load_start = time.perf_counter()
            load_fn = getattr(yaml_loader, "load_packs", None)
            if callable(load_fn):
                load_fn()
            else:  # pragma: no cover - legacy fallback
                yaml_loader.load_rule_packs()
            load_duration = max(time.perf_counter() - load_start, 0.0)

        # Build lookup helpers for dispatch artefact
        try:
            rule_lookup: Dict[str, Dict[str, Any]] = {
                str((spec.get("id") or spec.get("rule_id") or "")): spec
                for spec in getattr(yaml_loader, "_RULES", [])
                if spec.get("id") or spec.get("rule_id")
            }
        except Exception:
            rule_lookup = {}

        try:
            active_pack_records = yaml_loader.loaded_packs()
        except Exception:
            active_pack_records = []
        active_pack_set = {
            str(rec.get("path"))
            for rec in active_pack_records
            if isinstance(rec, dict) and rec.get("path")
        }
        active_packs = [
            rec.get("path")
            for rec in active_pack_records
            if isinstance(rec, dict) and rec.get("path")
        ]

        # 2) Candidate narrowing and per-segment evaluation
        doc_type_val = (
            getattr(snap, "doc_type", None)
            or getattr(snap, "type", "")
            or ""
        )

        for seg_id, seg_text, seg_start in segments_for_yaml:
            if not seg_text or not seg_text.strip():
                continue

            token = None
            try:
                candidate_ids = candidate_rules_by_segment.get(seg_id)
                if candidate_ids:
                    token = yaml_loader.CANDIDATES_VAR.set(set(candidate_ids))

                filtered_result = yaml_loader.filter_rules(
                    seg_text,
                    doc_type=doc_type_val,
                    clause_types=clause_types_set,
                    jurisdiction=jurisdiction,
                )
            finally:
                if token is not None:
                    yaml_loader.CANDIDATES_VAR.reset(token)

            if isinstance(filtered_result, tuple):
                filtered_rules = list(filtered_result[0] or [])
                coverage_entries = list(filtered_result[1] or [])
            else:
                filtered_rules = list(filtered_result or [])
                coverage_entries = []

            rules_payload = [item.get("rule") for item in filtered_rules]

            if filtered_rules:
                matched_rules.extend(filtered_rules)
                coverage_rules.extend(
                    [
                        {
                            "rule_id": item.get("rule", {}).get("id", ""),
                            "status": item.get("status", "matched"),
                        }
                        for item in filtered_rules
                    ]
                )

            if coverage_entries:
                for cov in coverage_entries:
                    rule_id = str(
                        cov.get("rule_id")
                        or cov.get("id")
                        or cov.get("rule", {}).get("id")
                        or ""
                    )
                    if not rule_id:
                        continue
                    evaluated_rule_ids.add(rule_id)
                    flags = 0
                    try:
                        flags = int(cov.get("flags") or 0)
                    except Exception:
                        flags = 0
                    if flags & getattr(yaml_loader, "FIRED", 0):
                        triggered_rule_ids.add(rule_id)

                    rule_spec = rule_lookup.get(rule_id, {})
                    triggers_spec = rule_spec.get("triggers") or {}
                    expected_any = [
                        getattr(pat, "pattern", str(pat))
                        for pat in triggers_spec.get("any", [])
                        if pat is not None
                    ]

                    evidence = cov.get("evidence") or []
                    spans = cov.get("spans") or []
                    matches: List[Dict[str, Any]] = []
                    for idx, span in enumerate(spans):
                        if not isinstance(span, Mapping):
                            continue
                        match_payload: Dict[str, Any] = {}
                        start_val = span.get("start")
                        end_val = span.get("end")
                        if isinstance(start_val, (int, float)):
                            match_payload["start"] = seg_start + int(start_val)
                        if isinstance(end_val, (int, float)):
                            match_payload["end"] = seg_start + int(end_val)
                        if idx < len(evidence) and evidence[idx] is not None:
                            match_payload["text"] = str(evidence[idx])
                        if match_payload:
                            matches.append(match_payload)

                    reason = None
                    if not (flags & getattr(yaml_loader, "FIRED", 0)):
                        reasons: List[str] = []
                        if flags & getattr(yaml_loader, "DOC_TYPE_MISMATCH", 0):
                            reasons.append("doc_type_mismatch")
                        if flags & getattr(yaml_loader, "JURISDICTION_MISMATCH", 0):
                            reasons.append("jurisdiction_mismatch")
                        if flags & getattr(yaml_loader, "NO_CLAUSE", 0):
                            reasons.append("requires_clause_missing")
                        if flags & getattr(yaml_loader, "REGEX_MISS", 0):
                            reasons.append("trigger_miss")
                        if flags & getattr(yaml_loader, "WHEN_FALSE", 0):
                            reasons.append("when_clause_false")
                        if flags & getattr(yaml_loader, "TEXT_NORMALIZATION_ISSUE", 0):
                            reasons.append("normalization_issue")
                        reason = ",".join(reasons) if reasons else None

                    pack_id = cov.get("pack_id") or rule_spec.get("pack")
                    packs_gate = True
                    if pack_id and active_pack_set:
                        packs_gate = str(pack_id) in active_pack_set

                    lang_gate = True
                    rule_langs_raw = rule_spec.get("language") or rule_spec.get(
                        "languages"
                    )
                    rule_langs: Set[str] = set()
                    if isinstance(rule_langs_raw, str):
                        rule_langs = {rule_langs_raw.lower()}
                    elif isinstance(rule_langs_raw, Iterable):
                        rule_langs = {
                            str(item).lower()
                            for item in rule_langs_raw
                            if item is not None and str(item).strip()
                        }
                    if rule_langs:
                        lang_gate = bool(doc_language) and doc_language in rule_langs

                    doctypes_gate = not bool(
                        flags & getattr(yaml_loader, "DOC_TYPE_MISMATCH", 0)
                    )

                    dispatch_candidates.append(
                        {
                            "rule_id": rule_id,
                            "gates": {
                                "packs": packs_gate,
                                "lang": lang_gate,
                                "doctypes": doctypes_gate,
                            },
                            "gates_passed": bool(packs_gate and lang_gate and doctypes_gate),
                            "expected_any": expected_any,
                            "matched": matches,
                            "reason_not_triggered": reason,
                        }
                    )
            run_start = time.perf_counter()
            findings_for_segment = yaml_engine.analyze(
                seg_text,
                [r for r in rules_payload if r is not None],
            )
            seg_run = max(time.perf_counter() - run_start, 0.0)
            engine_run_ms = (
                yaml_engine.meta.get("timings_ms", {}).get("run_rules_ms")
                if hasattr(yaml_engine, "meta")
                else None
            )
            if isinstance(engine_run_ms, (int, float)):
                seg_run = max(seg_run, float(engine_run_ms) / 1000.0)
            run_duration += seg_run

            if findings_for_segment and seg_start:
                for finding in findings_for_segment:
                    if not isinstance(finding, dict):
                        continue
                    start_val = finding.get("start")
                    if isinstance(start_val, (int, float)):
                        finding["start"] = seg_start + int(start_val)
                    end_val = finding.get("end")
                    if isinstance(end_val, (int, float)):
                        finding["end"] = seg_start + int(end_val)

            if findings_for_segment:
                yaml_findings.extend(findings_for_segment)

            for item in filtered_rules:
                rule = item.get("rule", {})
                matched: Dict[str, List[str]] = {}
                positions: List[Dict[str, int]] = []
                for kind, pats in (rule.get("triggers") or {}).items():
                    for pat in pats:
                        matches = list(pat.finditer(seg_text))
                        if matches:
                            matched.setdefault(kind, []).append(pat.pattern)
                            for m in matches:
                                positions.append(
                                    {
                                        "start": seg_start + m.start(),
                                        "end": seg_start + m.end(),
                                    }
                                )
                if matched:
                    fired_rules_meta.append(
                        {
                            "rule_id": rule.get("id"),
                            "pack": rule.get("pack"),
                            "matched_triggers": {
                                k: sorted(set(v)) for k, v in matched.items()
                            },
                            "requires_clause_hit": rule.get(
                                "requires_clause_hit", False
                            ),
                            "positions": positions,
                        }
                    )

        active_pack_records = yaml_loader.loaded_packs()
        active_packs = [
            rec.get("path")
            for rec in active_pack_records
            if isinstance(rec, dict) and rec.get("path")
        ]
        active_pack_set = {
            str(rec.get("path"))
            for rec in active_pack_records
            if isinstance(rec, dict) and rec.get("path")
        }
        rules_loaded = yaml_loader.rules_count()

        meta_map = {m["rule_id"]: m for m in fired_rules_meta}
        for f in yaml_findings:
            meta = meta_map.get(f.get("rule_id"))
            if meta:
                f["matched_triggers"] = meta.get("matched_triggers", {})
                f["trigger_positions"] = meta.get("positions", [])
    except Exception:
        log.exception("YAML dispatch pipeline failed")
        yaml_findings = []
        active_packs = []
        active_pack_set = set()
        rules_loaded = 0
        fired_rules_meta = []
        coverage_rules = []
        matched_rules = []
        load_duration = 0.0
        run_duration = 0.0

    if FEATURE_TRACE_ARTIFACTS:
        try:
            TRACE.add(
                request.state.cid,
                "dispatch",
                build_dispatch(
                    rules_loaded,
                    len(evaluated_rule_ids),
                    len(triggered_rule_ids),
                    dispatch_candidates,
                ),
            )
        except Exception:
            pass

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
        seg_filtered = [
            f
            for f in seg_findings
            if order.get(str(f.get("severity", "")).lower(), 1) >= thr
        ]
        if seg_filtered:
            findings = seg_filtered
        elif thr <= 1:
            findings = seg_findings[:1]
        elif seg_findings:
            f0 = dict(seg_findings[0])
            f0["severity"] = "high"
            findings = [f0]
        else:
            findings = []

    constraint_checks_iter: Sequence[Any] | List[Any] = []
    constraint_checks_populated = False
    if FEATURE_LX_ENGINE and LX_L2_CONSTRAINTS:
        try:
            pg = constraints.build_param_graph(snap, parsed.segments, lx_features)
            l2_results, constraint_checks_iter = constraints.eval_constraints(pg, findings)
            constraint_checks_populated = True
            l2_internal = [
                item for item in l2_results if isinstance(item, InternalFinding)
            ]
            l2_results_filtered = [
                item
                for item in l2_internal
                if order.get(str(getattr(item, "severity", "")).lower(), 1) >= thr
            ]
            if not l2_results_filtered and l2_internal:
                if thr <= 1:
                    l2_results_filtered = l2_internal[:1]
                else:
                    base_item = l2_internal[0]
                    try:
                        l2_results_filtered = [
                            base_item.model_copy(update={"severity": "high"})
                        ]
                    except Exception:
                        payload = base_item.model_dump()
                        payload["severity"] = "high"
                        l2_results_filtered = [InternalFinding(**payload)]
            if l2_results_filtered:
                findings = merge_findings(findings, l2_results_filtered)
        except Exception:
            pass

    if constraint_checks_populated:
        try:
            TRACE.add(
                request.state.cid,
                "constraints",
                build_constraints(constraint_checks_iter),
            )
        except Exception:
            pass

    _add_citations(findings)
    for f in findings:
        snip = f.get("snippet")
        if isinstance(snip, str):
            f["normalized_snippet"] = normalize_for_intake(snip)

    analysis_out = {"findings": findings, "status": "ok"}
    status_out = "ok"
    if os.getenv("FEATURE_LLM_ANALYZE", "0") == "1":
        pass

    snap.rules_count = asyncio.run(_discover_rules_count())
    summary = snap.model_dump()
    _ensure_legacy_doc_type(summary)
    # expose first detected clause type if any
    clause_type_val = next(iter(clause_types_set)) if clause_types_set else None
    summary.setdefault("clause_type", clause_type_val)
    companies_meta: List[Dict[str, Any]] = []
    try:
        parties = [
            Party(
                name=p.get("name", ""),
                company_number=p.get("company_number"),
                address=p.get("address"),
            )
            for p in summary.get("parties", [])
        ]
        doc_parties = [Party(**p.model_dump()) for p in parties]
        parties = enrich_parties_with_companies_house(parties)
        summary["parties"] = [p.model_dump() for p in parties]
        companies_meta = build_companies_meta(parties, doc_parties=doc_parties)
    except Exception:
        pass

    timings = {
        "parse_ms": round((t1 - t0) * 1000, 2),
        "classify_ms": round((t2 - t1) * 1000, 2),
        "load_rules_ms": round(load_duration * 1000, 2),
        "run_rules_ms": round(run_duration * 1000, 2),
    }

    debug_meta = {
        "pipeline": pipeline_id,
        "packs": active_packs,
        "rules_loaded": rules_loaded,
        "rules_evaluated": len(matched_rules),
        "rules_triggered": len(fired_rules_meta),
    }

    meta = {
        **PROVIDER_META,
        "document_type": summary.get("type"),
        "language": req.language,
        "text_bytes": len(txt.encode("utf-8")),
        "active_packs": active_packs,
        "rules_loaded_count": rules_loaded,
        "rules_fired_count": len(fired_rules_meta),
        "rules_evaluated": len(matched_rules),
        "fired_rules": fired_rules_meta,
        "pipeline_id": pipeline_id,
        "timings_ms": timings,
        "debug": debug_meta,
    }
    if companies_meta:
        meta["companies_meta"] = companies_meta

    log.info("analysis meta", extra={"meta": meta})

    envelope = {
        "status": status_out,
        "analysis": analysis_out,
        "results": {"summary": summary},
        "clauses": analysis_out.get("findings", []),
        "document": analysis_out.get("document", {}),
        "schema_version": SCHEMA_VERSION,
        "meta": meta,
        "summary": summary,
        # SSOT unified block
        "cid": request.state.cid,
        "findings": analysis_out.get("findings", []),
        "recommendations": [],
    }
    envelope["rules_coverage"] = {
        "doc_type": {"value": snap.type, "source": snap.type_source},
        "rules": coverage_rules,
    }
    IDEMPOTENCY_CACHE.set(req_hash, envelope)
    # also cache by response CID so summary lookups succeed
    IDEMPOTENCY_CACHE.set(request.state.cid, envelope)
    rec = {"resp": envelope, "cid": request.state.cid}
    an_cache.set(doc_hash, rec)
    cid_index.set(request.state.cid, {"hash": doc_hash})

    headers = {
        "x-cache": "miss",
        "x-cid": request.state.cid,
        "x-doc-hash": doc_hash,
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
    snap.rules_count = await _discover_rules_count()
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
    body: SummaryIn,
    mode: Optional[str] = None,
):
    t0 = _now_ms()
    _set_schema_headers(response)
    if body.cid:
        cached = IDEMPOTENCY_CACHE.get(body.cid)
        if not cached:
            resp = _problem_response(
                404,
                "cid not found",
                error_code="cid_not_found",
                detail="cid not found",
                cid=body.cid,
            )
            _set_std_headers(
                resp,
                cid=body.cid,
                xcache="miss",
                schema=SCHEMA_VERSION,
                latency_ms=_now_ms() - t0,
            )
            return resp
        summary = cached.get("summary") or cached.get("results", {}).get("summary", {})
        resp = {"status": "ok", "summary": summary, "meta": PROVIDER_META}
        _set_std_headers(
            response,
            cid=body.cid,
            xcache="hit",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        doc_meta = cid_index.get(body.cid)
        if doc_meta and "hash" in doc_meta:
            response.headers["x-doc-hash"] = doc_meta.get("hash", "")
        _set_llm_headers(response, PROVIDER_META)
        _ensure_legacy_doc_type(resp.get("summary"))
        return resp

    # body.hash is present (model ensures exactly one of cid or hash)
    rec = an_cache.get(body.hash)
    if not rec:
        resp = _problem_response(
            404,
            "hash not found",
            error_code="hash_not_found",
            detail="hash not found",
            cid=getattr(request.state, "cid", compute_cid(request)),
        )
        _set_std_headers(
            resp,
            cid=getattr(request.state, "cid", compute_cid(request)),
            xcache="miss",
            schema=SCHEMA_VERSION,
            latency_ms=_now_ms() - t0,
        )
        return resp

    summary = rec["resp"].get("summary") or rec["resp"].get("results", {}).get(
        "summary", {}
    )
    resp = {"status": "ok", "summary": summary, "meta": PROVIDER_META}
    response.headers["x-doc-hash"] = body.hash or ""
    _set_std_headers(
        response,
        cid=rec.get("cid", ""),
        xcache="hit",
        schema=SCHEMA_VERSION,
        latency_ms=_now_ms() - t0,
    )
    _set_llm_headers(response, PROVIDER_META)
    _ensure_legacy_doc_type(resp.get("summary"))
    return resp


# compatibility aliases at root level
@router.get("/summary")
async def summary_get_alias(response: Response, mode: Optional[str] = None):
    _set_schema_headers(response)
    return await api_summary_get(response, mode)


@router.post("/summary")
async def summary_post_alias(
    request: Request,
    response: Response,
    body: SummaryIn,
    mode: Optional[str] = None,
):
    return await api_summary_post(request, response, body, mode)


@router.post(
    "/api/qa-recheck",
    response_model=QARecheckOut,
)
async def api_qa_recheck(
    body: QARecheckIn,
    response: Response,
    x_cid: Optional[str] = Header(None),
    profile: str = "smart",
):
    t0 = _now_ms()
    _set_schema_headers(response)

    text = body.text
    rules = body.rules or {}
    cid = x_cid or _sha256_hex(str(t0) + text[:128])
    meta = LLM_CONFIG.meta()
    if LLM_CONFIG.provider == "azure" and not LLM_CONFIG.valid:
        resp = JSONResponse(
            status_code=401,
            content={
                "status": "error",
                "error_code": "provider_auth",
                "detail": "Azure key is invalid",
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
    mock_mode = mock_env or LLM_CONFIG.mode == "mock"
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
        payload = {"status": "ok", "qa": [], "meta": meta}
        payload.update(
            {
                "schema_version": SCHEMA_VERSION,
                "cid": cid,
                "summary": {"clause_type": None},
                "findings": [],
                "recommendations": [],
            }
        )
        return payload
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
    items = getattr(result, "items", [])
    payload = {"status": "ok", "qa": items, "meta": meta}
    payload.update(
        {
            "schema_version": SCHEMA_VERSION,
            "cid": cid,
            "summary": {"clause_type": None},
            "findings": items,
            "recommendations": [],
        }
    )
    return payload


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
    if not isinstance(text, str) or text.strip() == "":
        raise HTTPException(status_code=422, detail="text required")
    findings_raw = (payload or {}).get("findings")
    if findings_raw is None:
        findings_raw = []
    elif isinstance(findings_raw, dict):
        findings_raw = [findings_raw]
    elif not isinstance(findings_raw, list):
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

    cid = x_cid or getattr(request.state, "cid", _PROCESS_CID)
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
        proposed_text = (
            proposed_text[: op["start"]]
            + op["replacement"]
            + proposed_text[op["end"] :]
        )
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
    "/api/gpt/draft",
    response_model=DraftResponse,
    responses={422: {"model": ProblemDetail}},
)
async def gpt_draft(inp: DraftRequest):
    """Simplified LLM draft endpoint with strict validation."""

    # In this simplified version we just echo back a draft based on the clause.
    draft_text = f"Draft: {inp.clause.strip()}"
    return DraftResponse(draft=draft_text)


@router.post(
    "/api/gpt-draft",
    response_model=DraftResponse,
    responses={422: {"model": ProblemDetail}},
)
async def gpt_draft_alias(req: DraftRequest):
    return await gpt_draft(req)


@router.post(
    "/api/panel/redlines",
    response_model=RedlinesOut,
)
def panel_redlines(inp: RedlinesIn, request: Request):
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
    return api_analyze(request, req.model_dump())


@router.post("/suggest_edits")
async def suggest_edits_alias(
    request: Request, response: Response, x_cid: Optional[str] = Header(None)
):
    return await api_suggest_edits(request, response, x_cid)


@router.post(
    "/api/draft",
    response_model=DraftResponse,
    responses={422: {"model": ProblemDetail}},
)
async def draft_alias(req: DraftRequest):
    return await gpt_draft(req)


@app.get("/llm/ping")
def llm_ping_alias():
    return llm_ping()


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
            413,
            "Payload too large",
            error_code="payload_too_large",
            detail="Request body exceeds limits",
            cid=x_cid or getattr(request.state, "cid", _PROCESS_CID),
        )
    except Exception:
        return _problem_response(
            400,
            "Bad JSON",
            error_code="bad_json",
            detail="Request body is not valid JSON",
            cid=x_cid or getattr(request.state, "cid", _PROCESS_CID),
        )

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
    ok = True
    try:
        LEARNING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        secure_write(
            LEARNING_LOG_PATH, json.dumps(body, ensure_ascii=False), append=True
        )
    except Exception as exc:  # pragma: no cover - best effort logging
        log.warning("failed to write learning log: %s", exc, exc_info=True)
        ok = False
    resp = Response(status_code=204)
    resp.headers["x-learning-log-status"] = "ok" if ok else "error"
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
async def api_citation_resolve(
    body: CitationResolveRequest,
    response: Response,
    x_cid: str | None = Header(None),
):
    t0 = _now_ms()
    if body.citations is not None:
        citations = body.citations
    else:
        citations: list[CitationInput] = []
        for f in body.findings or []:
            try:
                core = CoreFinding.model_validate(
                    {
                        "code": f.code or "",
                        "message": f.message or "",
                        "rule": f.rule or "",
                    }
                )
            except Exception:
                continue
            c = resolve_citation(core)
            if c is None:
                continue
            citations.append(CitationInput(instrument=c.instrument, section=c.section))
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
