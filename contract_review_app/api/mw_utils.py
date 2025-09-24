import json
from typing import Tuple


async def capture_response(response) -> Tuple[bytes, dict, str]:
    chunks = []
    async for section in response.body_iterator:
        chunks.append(section)
    body = b"".join(chunks)
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return body, headers, response.media_type or "application/octet-stream"


def normalize_status_if_json(body: bytes, media_type: str) -> bytes:
    if not body or not media_type.startswith("application/json"):
        return body
    try:
        payload = json.loads(body)
        if isinstance(payload, dict) and isinstance(payload.get("status"), str):
            payload["status"] = payload["status"].lower()
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")
    except Exception:
        return body
