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

    In DEV mode (``DEV_MODE`` truthy) missing headers may be filled from
    environment defaults when ``ALLOW_DEV_KEY_INJECTION`` is also truthy. When
    this auto-injection occurs a warning is logged. Otherwise missing
    ``x-api-key`` results in ``401``. In production, ``x-api-key`` must match
    ``API_KEY`` when ``FEATURE_REQUIRE_API_KEY`` is truthy and
    ``x-schema-version`` must equal the current ``SCHEMA_VERSION`` (``1.4``)."""

    dev_mode = _env_truthy("DEV_MODE")
    allow_injection = _env_truthy("ALLOW_DEV_KEY_INJECTION")

    if dev_mode and allow_injection:
        headers = request.headers
        api_key = headers.get("x-api-key")
        schema = headers.get("x-schema-version")
        if not api_key:
            api_key = os.getenv("DEFAULT_API_KEY", "local-test-key-123")
            log.warning("auto-filling missing x-api-key header in dev mode")
        if not schema:
            schema = os.getenv("SCHEMA_VERSION", SCHEMA_VERSION)
            log.warning("auto-filling missing x-schema-version header in dev mode")
        request.state.api_key = api_key
        request.state.schema_version = schema
        return
    elif dev_mode and not request.headers.get("x-api-key"):
        log.info("reject: missing x-api-key and dev injection disabled")
        raise HTTPException(status_code=401, detail="missing or invalid api key")

    if _env_truthy("FEATURE_REQUIRE_API_KEY"):
        api_key = os.getenv("API_KEY", "")
        if request.headers.get("x-api-key") != api_key:
            log.info("reject: missing or invalid x-api-key")
            raise HTTPException(status_code=401, detail="missing or invalid api key")
    request.state.api_key = request.headers.get("x-api-key")

    schema = request.headers.get("x-schema-version")
    if not schema:
        log.info("reject: missing x-schema-version header")
        raise HTTPException(
            status_code=400, detail="x-schema-version header is required"
        )
    if schema != SCHEMA_VERSION:
        log.info("reject: unsupported x-schema-version %s", schema)
        raise HTTPException(status_code=400, detail="unsupported schema version")
    request.state.schema_version = schema
