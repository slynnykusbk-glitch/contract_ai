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

    ``x-api-key`` must match ``API_KEY`` when ``FEATURE_REQUIRE_API_KEY`` is
    truthy. ``x-schema-version`` is always required and must equal the
    current ``SCHEMA_VERSION`` (``1.4``)."""
    if _env_truthy("FEATURE_REQUIRE_API_KEY"):
        api_key = os.getenv("API_KEY", "")
        if request.headers.get("x-api-key") != api_key:
            log.info("reject: missing or invalid x-api-key")
            raise HTTPException(status_code=401, detail="missing or invalid api key")

    schema = request.headers.get("x-schema-version")
    if not schema:
        log.info("reject: missing x-schema-version header")
        raise HTTPException(status_code=400, detail="x-schema-version header is required")
    if schema != SCHEMA_VERSION:
        log.info("reject: unsupported x-schema-version %s", schema)
        raise HTTPException(status_code=400, detail="unsupported schema version")
