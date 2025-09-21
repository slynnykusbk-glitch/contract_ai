import os
import time
import random
import logging
from typing import Any, Dict

import httpx

from contract_review_app.api.limits import CH_TIMEOUT_S
from contract_review_app.config import CH_API_KEY, CH_ENABLED

log = logging.getLogger("contract_ai")

BASE_URL = os.getenv("COMPANIES_HOUSE_BASE", "https://api.company-information.service.gov.uk")
TIMEOUT_S = float(CH_TIMEOUT_S)
CACHE_TTL = int(os.getenv("CH_CACHE_TTL", str(20 * 60)))  # default 20 minutes

# cache keyed by endpoint path
_CACHE: Dict[str, Dict[str, Any]] = {}


class CHError(Exception):
    """Generic Companies House error."""


def _request(path: str) -> Dict[str, Any]:
    if not CH_ENABLED:
        raise CHError("companies house disabled")

    url = f"{BASE_URL}{path}"
    cached = _CACHE.get(url)
    now = time.time()
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["data"]

    auth = (CH_API_KEY or "", "")
    # simple retry with backoff and jitter for 429
    for attempt in range(3):
        if attempt:
            # exponential backoff with jitter up to 1s
            delay = (2 ** (attempt - 1)) + random.random()
            time.sleep(delay)
        resp = httpx.get(url, auth=auth, timeout=TIMEOUT_S)
        if resp.status_code == 429:
            continue
        if resp.status_code != 200:
            raise CHError(f"bad status: {resp.status_code}")
        data = resp.json()
        _CACHE[url] = {"data": data, "ts": now}
        return data
    raise CHError("rate limited")


def get_company(company_number: str) -> Dict[str, Any]:
    return _request(f"/company/{company_number}")


def get_officers(company_number: str) -> Dict[str, Any]:
    return _request(f"/company/{company_number}/officers")


def get_filing_history(company_number: str) -> Dict[str, Any]:
    return _request(f"/company/{company_number}/filing-history")


def get_psc(company_number: str) -> Dict[str, Any]:
    return _request(
        f"/company/{company_number}/persons-with-significant-control"
    )
