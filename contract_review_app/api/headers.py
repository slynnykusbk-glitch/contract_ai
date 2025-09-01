import hashlib
import json
import time
from typing import Any

from fastapi import Request, Response

from .models import SCHEMA_VERSION


def compute_cid(request: Request) -> str:
    """Compute deterministic content id for a request.

    POST/PUT/PATCH: path + sorted(query) + canonical JSON body
    GET/DELETE: path + sorted(query)
    """
    path = request.url.path
    query_items = sorted(request.query_params.multi_items())
    query = "&".join(f"{k}={v}" for k, v in query_items)
    body_part = ""
    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        body_bytes = getattr(request.state, "body", b"")
        try:
            obj: Any = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
        except Exception:
            obj = body_bytes.decode("utf-8", "ignore")
        if obj is None:
            body_part = ""
        elif isinstance(obj, (dict, list)):
            body_part = json.dumps(obj, sort_keys=True, ensure_ascii=False)
        else:
            body_part = str(obj)
    raw = f"{path}{query}{body_part}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def apply_std_headers(response: Response, request: Request, started_at: float) -> None:
    """Apply standard headers to the response."""
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    cid = compute_cid(request)
    response.headers["x-schema-version"] = SCHEMA_VERSION
    response.headers["x-latency-ms"] = str(latency_ms)
    response.headers["x-cid"] = cid
