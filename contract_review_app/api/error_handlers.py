"""Centralised error handlers for FastAPI application.

This module defines a tiny and stable error vocabulary exposed to the
frontend.  All responses are small JSON objects with a single
``detail`` field so the client does not need to parse large pydantic
structures.
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .errors import UpstreamTimeoutError
from .headers import apply_std_headers


log = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register standardised error handlers on the application."""

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        log.warning("validation error: %s", exc)
        resp = JSONResponse({"detail": "validation error"}, status_code=422)
        apply_std_headers(resp, request, getattr(request.state, "started_at", time.perf_counter()))
        return resp

    @app.exception_handler(UpstreamTimeoutError)
    async def _timeout_error(request: Request, exc: UpstreamTimeoutError):
        resp = JSONResponse({"detail": "upstream timeout"}, status_code=504)
        apply_std_headers(resp, request, getattr(request.state, "started_at", time.perf_counter()))
        return resp

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception):
        # HTTPException carries explicit status/detail; everything else maps to 500
        if isinstance(exc, HTTPException):
            status = exc.status_code
            detail = exc.detail if isinstance(exc.detail, str) else "internal error"
        else:
            log.exception("unhandled exception", exc_info=exc)
            status = 500
            detail = "internal error"

        resp = JSONResponse({"detail": detail}, status_code=status)
        apply_std_headers(resp, request, getattr(request.state, "started_at", time.perf_counter()))
        return resp

