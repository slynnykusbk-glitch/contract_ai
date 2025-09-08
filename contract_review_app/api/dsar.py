import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, Depends

from contract_review_app.security.secure_store import secure_read
from .auth import require_api_key_and_schema

_DATA_DIR = Path(__file__).resolve().parents[2] / "var" / "dsar"

router = APIRouter(prefix="/api/dsar")


def _verify_token(token: str) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="invalid token")


@router.get("/access", dependencies=[Depends(require_api_key_and_schema)])
async def dsar_access(identifier: str, token: str):
    _verify_token(token)
    path = _DATA_DIR / f"{identifier}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(secure_read(path).decode("utf-8"))
    except Exception:
        data = {}
    return data


@router.post("/erasure", dependencies=[Depends(require_api_key_and_schema)])
async def dsar_erasure(identifier: str, token: str):
    _verify_token(token)
    path = _DATA_DIR / f"{identifier}.json"
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass
    return {"status": "ok"}


@router.get("/export", dependencies=[Depends(require_api_key_and_schema)])
async def dsar_export(identifier: str, token: str):
    _verify_token(token)
    path = _DATA_DIR / f"{identifier}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    data = secure_read(path)
    headers = {"Content-Disposition": f"attachment; filename={identifier}.json"}
    return Response(content=data, media_type="application/json", headers=headers)


__all__ = ["router"]
