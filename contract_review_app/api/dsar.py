from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

from contract_review_app.security.secure_store import secure_read

API_KEY = os.getenv("API_KEY", "")
_DATA_DIR = Path(__file__).resolve().parents[2] / "var" / "dsar"

router = APIRouter(prefix="/api/dsar")


def _check_api_key(request: Request) -> None:
    if request.headers.get("x-api-key") != API_KEY:
        raise HTTPException(status_code=401, detail="missing or invalid api key")


def _verify_token(token: str) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="invalid token")


@router.get("/access")
async def dsar_access(identifier: str, token: str, request: Request):
    _check_api_key(request)
    _verify_token(token)
    path = _DATA_DIR / f"{identifier}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(secure_read(path).decode("utf-8"))
    except Exception:
        data = {}
    return data


@router.post("/erasure")
async def dsar_erasure(identifier: str, token: str, request: Request):
    _check_api_key(request)
    _verify_token(token)
    path = _DATA_DIR / f"{identifier}.json"
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass
    return {"status": "ok"}


@router.get("/export")
async def dsar_export(identifier: str, token: str, request: Request):
    _check_api_key(request)
    _verify_token(token)
    path = _DATA_DIR / f"{identifier}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    data = secure_read(path)
    headers = {"Content-Disposition": f"attachment; filename={identifier}.json"}
    return Response(content=data, media_type="application/json", headers=headers)


__all__ = ["router"]
