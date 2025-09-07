import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, Response

from contract_review_app.integrations.companies_house import client as ch_client

router = APIRouter(prefix="/api", tags=["integrations"])


def _disabled() -> bool:
    return os.getenv("FEATURE_COMPANIES_HOUSE", "0") != "1" or not ch_client.KEY


def _cache_headers(etag: str, cache: str) -> dict:
    return {"ETag": etag, "x-cache": cache, "Cache-Control": "public, max-age=600"}


@router.post("/companies/search")
async def api_companies_search(payload: dict, request: Request):
    if _disabled():
        raise HTTPException(status_code=503, detail={"error": "CH integration disabled"})
    try:
        data = ch_client.search_companies(str(payload.get("q", "")), int(payload.get("items", 10)))
    except ch_client.CHTimeout:
        raise HTTPException(status_code=504, detail={"error": "ch_timeout"})
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


@router.get("/companies/{number}")
async def api_company_profile(number: str, request: Request):
    if _disabled():
        raise HTTPException(status_code=503, detail={"error": "CH integration disabled"})
    try:
        data = ch_client.get_company_profile(number)
    except ch_client.CHTimeout:
        raise HTTPException(status_code=504, detail={"error": "ch_timeout"})
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
