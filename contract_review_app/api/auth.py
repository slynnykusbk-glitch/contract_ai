from __future__ import annotations

import os
import logging
from fastapi import HTTPException, Request

from .models import SCHEMA_VERSION

log = logging.getLogger("contract_ai")

_TRUTHY = {"1", "true", "yes", "on", "enabled"}


def _env_truthy(name: str) -> bool:
    return (os.getenv(name, "") or "").strip().lower() in _TRUTHY


def require_api_key_and_schema(request: Request) -> None:
    """Validate required request headers.

    In DEV mode (``DEV_MODE`` truthy) missing headers are filled from environment
    defaults and no errors are raised. In production, ``x-api-key`` must match
    ``API_KEY`` when ``FEATURE_REQUIRE_API_KEY`` is truthy and
    ``x-schema-version`` must equal the current ``SCHEMA_VERSION`` (``1.4``)."""

    dev_mode = _env_truthy("DEV_MODE")
    if dev_mode:
        headers = request.headers
        api_key = headers.get("x-api-key") or os.getenv(
            "DEFAULT_API_KEY", "local-test-key-123"
        )
        schema = headers.get("x-schema-version") or os.getenv(
            "SCHEMA_VERSION", SCHEMA_VERSION
        )
        request.state.api_key = api_key
        request.state.schema_version = schema
        return

    if _env_truthy("FEATURE_REQUIRE_API_KEY"):
        api_key = os.getenv("API_KEY", "")
        if request.headers.get("x-api-key") != api_key:
            log.info("reject: missing or invalid x-api-key")
            raise HTTPException(status_code=401, detail="missing or invalid api key")
    request.state.api_key = request.headers.get("x-api-key")

    schema = request.headers.get("x-schema-version")
    if not schema:
        log.info("reject: missing x-schema-version header")
        raise HTTPException(status_code=400, detail="x-schema-version header is required")
    if schema != SCHEMA_VERSION:
        log.info("reject: unsupported x-schema-version %s", schema)
        raise HTTPException(status_code=400, detail="unsupported schema version")
    request.state.schema_version = schema
