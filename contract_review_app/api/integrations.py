from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from pydantic import BaseModel, ConfigDict, Field

from contract_review_app.config import CH_ENABLED, CH_API_KEY, FEATURE_COMPANIES_HOUSE
from contract_review_app.integrations.companies_house import client as ch_client

router = APIRouter(prefix="/api", tags=["integrations"])


class _CompanySearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    items: int = 10


def _cache_headers(etag: str, cache: str) -> dict:
    return {"ETag": etag, "x-cache": cache, "Cache-Control": "public, max-age=600"}


def _companies_search(query: str, items: int, request: Request):
    try:
        data = ch_client.search_companies(query, items)
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
    return JSONResponse(data, headers=headers)


def _ch_gate() -> JSONResponse | None:
    if FEATURE_COMPANIES_HOUSE in {"1", "true", "True"} and not CH_API_KEY:
        return JSONResponse(
            {"error": "companies_house_api_key_missing"},
            status_code=401,
        )
    if not CH_ENABLED:
        return JSONResponse(
            {"error": "companies_house_disabled", "hint": "Set FEATURE_COMPANIES_HOUSE=1 and CH_API_KEY=..."},
            status_code=503,
        )
    return None


@router.post("/companies/search")
async def api_companies_search(payload: _CompanySearchIn, request: Request):
    gate = _ch_gate()
    if gate:
        return gate
    return _companies_search(payload.query, payload.items, request)


@router.get("/companies/search")
async def api_companies_search_get(q: str, request: Request, items: int = 10):
    gate = _ch_gate()
    if gate:
        return gate
    return _companies_search(q, items, request)


@router.get("/companies/{number}")
async def api_company_profile(number: str, request: Request):
    gate = _ch_gate()
    if gate:
        return gate
    try:
        data = ch_client.get_company_profile(number)
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
    return JSONResponse(data, headers=headers)
