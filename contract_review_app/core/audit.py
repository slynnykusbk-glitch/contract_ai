from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional


_LOGGER: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    os.makedirs("var", exist_ok=True)
    logger = logging.getLogger("audit")
    if not logger.handlers:
        handler = RotatingFileHandler(
            os.path.join("var", "audit.log"), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    _LOGGER = logger
    return logger


def audit(event: str, user: Optional[str], doc_hash: Optional[str], details: Dict[str, Any]) -> None:
    """Write audit entry as JSON line.

    Parameters mirror the required audit fields. ``details`` is merged at the
    top level to allow callers to record additional counters/metadata.
    """

    logger = _get_logger()
    record: Dict[str, Any] = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "user": user,
        "doc_hash": doc_hash,
    }
    if details:
        record.update(details)
    logger.info(json.dumps(record, sort_keys=True))


__all__ = ["audit"]
