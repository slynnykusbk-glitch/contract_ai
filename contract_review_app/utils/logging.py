from __future__ import annotations

"""Central logging configuration using loguru and optional Sentry."""

import os
import sys

try:
    from loguru import logger  # type: ignore
except Exception:  # loguru отсутствует — уходим в stdlib
    import logging as _pylog

    logger = _pylog.getLogger("contract_ai")
    if not logger.handlers:
        _h = _pylog.StreamHandler()
        _pylog.basicConfig(level=_pylog.INFO)
        logger.addHandler(_h)


def init_logging() -> logger.__class__:
    """Configure loguru logger and optional Sentry integration.

    The log level is controlled by the ``CAI_DEBUG`` environment variable.
    When ``SENTRY_DSN`` is provided, Sentry is initialised for error reporting.
    """
    debug = os.getenv("CAI_DEBUG") == "1"
    logger.remove()
    logger.add(
        sys.stderr, level="DEBUG" if debug else "INFO", backtrace=True, diagnose=debug
    )

    dsn = os.getenv("SENTRY_DSN")
    if dsn:
        try:  # optional dependency
            import sentry_sdk  # type: ignore

            sentry_sdk.init(dsn=dsn)
            logger.debug("Sentry initialised")
        except Exception as e:  # pragma: no cover - diagnostics only
            logger.warning("Failed to init Sentry: {0}", e)

    return logger


__all__ = ["init_logging", "logger"]
