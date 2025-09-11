import os
import time
import json
from typing import Dict, Any

import httpx

from contract_review_app.core.audit import audit

BASE = os.getenv(
    "COMPANIES_HOUSE_BASE", "https://api.company-information.service.gov.uk"
)
KEY = (os.getenv("CH_API_KEY") or os.getenv("COMPANIES_HOUSE_API_KEY", "")).strip()
TIMEOUT_S = float(os.getenv("CH_TIMEOUT_S", "8"))

_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST: Dict[str, str] = {}


class CHError(Exception):
    pass


class CHTimeout(CHError):
    pass


class CHNotFound(CHError):
    pass


class CHRateLimited(CHError):
    def __init__(self, retry_after: str | None = None):
        super().__init__("rate limited")
        self.retry_after = retry_after


def get_last_headers() -> Dict[str, str]:
    return _LAST.copy()


def _do_get(url: str) -> dict:
    cached = _CACHE.get(url)
    headers = {}
    if cached and cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    auth = (KEY, "")
    start = time.time()
    resp: httpx.Response | None = None
    for attempt, delay in enumerate([0.0, 0.4, 0.8]):
        if delay:
            time.sleep(delay)
        try:
            resp = httpx.get(url, headers=headers, auth=auth, timeout=TIMEOUT_S)
        except httpx.TimeoutException as e:
            audit(
                "integration_call",
                None,
                None,
                {
                    "provider": "ch",
                    "path": url.replace(BASE, "").split("?")[0],
                    "status": "timeout",
                    "latency_ms": int((time.time() - start) * 1000),
                    "cache": _LAST.get("cache", "miss"),
                },
            )
            raise CHTimeout("companies house timeout") from e
        if resp.status_code in [429] or (
            500 <= resp.status_code < 600 and resp.status_code not in (501, 505)
        ):
            if attempt < 2:
                continue
        break
    if resp is None:
        raise CHError("no response")
    cache_status = "miss"
    if resp.status_code == 304 and cached:
        data = json.loads(cached["body"])
        etag = cached.get("etag", "")
        cache_status = "hit"
    elif resp.status_code == 200:
        etag = resp.headers.get("ETag", "")
        _CACHE[url] = {"etag": etag, "body": resp.content, "ts": time.time()}
        data = resp.json()
    elif resp.status_code == 404:
        audit(
            "integration_call",
            None,
            None,
            {
                "provider": "ch",
                "path": url.replace(BASE, "").split("?")[0],
                "status": resp.status_code,
                "latency_ms": int((time.time() - start) * 1000),
                "cache": cache_status,
            },
        )
        raise CHNotFound("not found")
    elif resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        audit(
            "integration_call",
            None,
            None,
            {
                "provider": "ch",
                "path": url.replace(BASE, "").split("?")[0],
                "status": resp.status_code,
                "latency_ms": int((time.time() - start) * 1000),
                "cache": cache_status,
            },
        )
        raise CHRateLimited(retry_after)
    elif (
        500 <= resp.status_code < 600 and resp.status_code not in (501, 505) and cached
    ):
        data = json.loads(cached["body"])
        etag = cached.get("etag", "")
        cache_status = "stale"
    else:
        audit(
            "integration_call",
            None,
            None,
            {
                "provider": "ch",
                "path": url.replace(BASE, "").split("?")[0],
                "status": resp.status_code,
                "latency_ms": int((time.time() - start) * 1000),
                "cache": cache_status,
            },
        )
        raise CHError(f"bad status: {resp.status_code}")
    _LAST["etag"] = etag
    _LAST["cache"] = cache_status
    audit(
        "integration_call",
        None,
        None,
        {
            "provider": "ch",
            "path": url.replace(BASE, "").split("?")[0],
            "status": resp.status_code,
            "latency_ms": int((time.time() - start) * 1000),
            "cache": cache_status,
        },
    )
    return data


def search_companies(q: str, items: int = 10) -> dict:
    params = httpx.QueryParams({"q": q, "items_per_page": items})
    url = f"{BASE}/search/companies?{params}"
    return _do_get(url)


def get_company_profile(company_number: str) -> dict:
    url = f"{BASE}/company/{company_number}"
    return _do_get(url)


def get_officers_count(company_number: str) -> int:
    url = f"{BASE}/company/{company_number}/officers?items_per_page=1"
    data = _do_get(url)
    return int(data.get("total_results", 0))


def get_psc_count(company_number: str) -> int:
    url = f"{BASE}/company/{company_number}/persons-with-significant-control?items_per_page=1"
    data = _do_get(url)
    return int(data.get("total_results", 0))
