from __future__ import annotations

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .models import SCHEMA_VERSION


class RequireHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce header policy and inject standard response headers."""

    async def dispatch(self, request: Request, call_next):
        method = request.method.upper()
        headers = request.headers

        # store cid and schema for downstream handlers
        request.state.cid = headers.get("x-cid") or uuid.uuid4().hex
        request.state.schema_version = headers.get("x-schema-version") or SCHEMA_VERSION

        if method in {"POST", "PUT", "PATCH"}:
            if "x-api-key" not in headers:
                return JSONResponse({"detail": "missing x-api-key"}, status_code=401)
            if "x-schema-version" not in headers:
                return JSONResponse(
                    {"detail": "missing x-schema-version"}, status_code=400
                )

        response = await call_next(request)

        if 200 <= response.status_code < 400:
            response.headers["x-schema-version"] = SCHEMA_VERSION
            if request.url.path == "/api/analyze":
                cid = response.headers.get("x-cid") or request.state.cid
                response.headers["X-Cid"] = cid
        return response
