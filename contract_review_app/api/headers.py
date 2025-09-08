import time

from fastapi import Request, Response

from contract_review_app.core.trace import compute_cid

from .models import SCHEMA_VERSION


def apply_std_headers(response: Response, request: Request, started_at: float) -> None:
    """Apply standard headers to the response."""
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    cid = compute_cid(request)
    response.headers["x-schema-version"] = SCHEMA_VERSION
    response.headers["x-latency-ms"] = str(latency_ms)
    response.headers["x-cid"] = cid
