from __future__ import annotations

import os


def env_int(name: str, default: int) -> int:
    """Read ``name`` from the environment as an integer."""

    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):  # tolerate floats or junk values
        try:
            return int(float(str(raw)))
        except (TypeError, ValueError):
            return default


# API limits
API_TIMEOUT_S = env_int("CONTRACTAI_API_TIMEOUT_S", 60)
REQUEST_TIMEOUT_S = env_int("CONTRACTAI_REQUEST_TIMEOUT_S", 75)
API_RATE_LIMIT_PER_MIN = env_int("CONTRACTAI_RATE_PER_MIN", 60)
DEFAULT_PAGE_SIZE = env_int("CONTRACTAI_PAGE_SIZE", 10)
MAX_PAGE_SIZE = env_int("CONTRACTAI_MAX_PAGE_SIZE", 50)

# Orchestrator budgets
ANALYZE_TIMEOUT_S = env_int("CONTRACT_AI_ANALYZE_TIMEOUT_SEC", 55)
QA_TIMEOUT_S = env_int("CONTRACT_AI_QA_TIMEOUT_SEC", 40)
DRAFT_TIMEOUT_S = env_int("CONTRACT_AI_DRAFT_TIMEOUT_SEC", 40)

# External calls
LLM_TIMEOUT_S = env_int("LLM_TIMEOUT_S", 40)
CH_TIMEOUT_S = env_int("CH_TIMEOUT_S", 10)


__all__ = [
    "API_TIMEOUT_S",
    "REQUEST_TIMEOUT_S",
    "API_RATE_LIMIT_PER_MIN",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "ANALYZE_TIMEOUT_S",
    "QA_TIMEOUT_S",
    "DRAFT_TIMEOUT_S",
    "LLM_TIMEOUT_S",
    "CH_TIMEOUT_S",
    "env_int",
]
