from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from pydantic import BaseModel, ConfigDict, Field

from contract_review_app.config import CH_ENABLED, CH_API_KEY, FEATURE_COMPANIES_HOUSE
from contract_review_app.integrations.companies_house import client as ch_client

router = APIRouter(prefix="/api", tags=["integrations"])


class _CompanySearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    limit: int = 10


def _cache_headers(etag: str, cache: str) -> dict:
    return {"ETag": etag, "x-cache": cache, "Cache-Control": "public, max-age=600"}


def _normalize_profile(data: dict, officers: int, psc: int) -> dict:
    roa = data.get("registered_office_address") or {}
    address_parts = [
        roa.get("care_of"),
        roa.get("po_box"),
        roa.get("premises"),
        roa.get("address_line_1"),
        roa.get("address_line_2"),
    ]
    address_line = ", ".join([p for p in address_parts if p]) or None
    accounts = data.get("accounts") or {}
    confirmation = data.get("confirmation_statement") or {}
    return {
        "company_number": data.get("company_number"),
        "company_name": data.get("company_name"),
        "status": data.get("company_status"),
        "company_type": data.get("type"),
        "jurisdiction": data.get("jurisdiction"),
        "incorporated_on": data.get("date_of_creation"),
        "registered_office": {
            "address_line": address_line,
            "postcode": roa.get("postal_code"),
            "locality": roa.get("locality"),
            "country": roa.get("country"),
        },
        "sic_codes": data.get("sic_codes", []) or [],
        "accounts": {
            "last_made_up_to": (accounts.get("last_accounts") or {}).get("made_up_to"),
            "next_due": (accounts.get("next_accounts") or {}).get("due_on"),
        },
        "confirmation_statement": {
            "last_made_up_to": confirmation.get("last_made_up_to"),
            "next_due": confirmation.get("next_due"),
        },
        "officers_count": officers,
        "psc_count": psc,
    }


def _companies_search(query: str, limit: int, request: Request):
    try:
        data = ch_client.search_companies(query, limit)
    except ch_client.CHTimeout:
        raise HTTPException(status_code=503, detail={"error": "ch_timeout"})
    except ch_client.CHError:
        raise HTTPException(status_code=502, detail={"error": "ch_error"})
    meta = ch_client.get_last_headers()
    etag = meta.get("etag", "")
    cache = meta.get("cache", "miss")
    inm = request.headers.get("if-none-match")
    headers = _cache_headers(etag, cache)
    if inm and inm == etag and cache == "hit":
        return Response(status_code=304, headers=headers)
    items = data.get("items") or []
    norm = [
        {
            "company_number": item.get("company_number"),
            "company_name": item.get("title"),
            "address_snippet": item.get("address_snippet"),
            "status": item.get("company_status"),
        }
        for item in items
    ]
    return JSONResponse(norm, headers=headers)


def _ch_gate() -> JSONResponse | None:
    if FEATURE_COMPANIES_HOUSE in {"1", "true", "True"} and not CH_API_KEY:
        return JSONResponse(
            {"error": "companies_house_api_key_missing"},
            status_code=401,
        )
    if not CH_ENABLED:
        return JSONResponse(
            {
                "error": "companies_house_disabled",
                "hint": "Set FEATURE_COMPANIES_HOUSE=1 and CH_API_KEY=...",
            },
            status_code=503,
        )
    return None


@router.get("/companies/health")
async def companies_health():
    if not CH_ENABLED:
        return JSONResponse({"status": "disabled"}, status_code=403)
    return {"companies_house": "ok"}


@router.post("/companies/search")
async def api_companies_search(payload: _CompanySearchIn, request: Request):
    gate = _ch_gate()
    if gate:
        return gate
    return _companies_search(payload.query, payload.limit, request)


@router.get("/companies/search")
async def api_companies_search_get(q: str, request: Request, limit: int = 10):
    gate = _ch_gate()
    if gate:
        return gate
    return _companies_search(q, limit, request)


@router.get("/companies/{number}")
async def api_company_profile(number: str, request: Request):
    gate = _ch_gate()
    if gate:
        return gate
    try:
        data = ch_client.get_company_profile(number)
    except ch_client.CHNotFound:
        return JSONResponse({"error": "company_not_found"}, status_code=404)
    except ch_client.CHRateLimited as e:
        headers = {"Retry-After": e.retry_after} if e.retry_after else None
        return JSONResponse({"error": "rate_limited"}, status_code=429, headers=headers)
    except ch_client.CHTimeout:
        return JSONResponse({"error": "ch_timeout"}, status_code=503)
    except ch_client.CHError:
        return JSONResponse({"error": "ch_error"}, status_code=502)
    meta = ch_client.get_last_headers()
    etag = meta.get("etag", "")
    cache = meta.get("cache", "miss")
    inm = request.headers.get("if-none-match")
    headers = _cache_headers(etag, cache)
    if inm and inm == etag and cache == "hit":
        return Response(status_code=304, headers=headers)
    officers = 0
    psc = 0
    try:
        officers = ch_client.get_officers_count(number)
    except ch_client.CHError:
        pass
    try:
        psc = ch_client.get_psc_count(number)
    except ch_client.CHError:
        pass
    norm = _normalize_profile(data, officers, psc)
    return JSONResponse(norm, headers=headers)
