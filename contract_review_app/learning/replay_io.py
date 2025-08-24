# contract_review_app/learning/replay_io.py
from __future__ import annotations
import os, json, gzip, time, uuid, hashlib, hmac
from datetime import datetime
from typing import List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # contract_review_app/
LEARNING_DIR = os.path.join(BASE_DIR, "learning")
REPLAY_FILE = os.path.join(LEARNING_DIR, "replay_buffer.jsonl")
HMAC_KEY_FILE = os.path.join(LEARNING_DIR, ".hmac.key")
MAX_EVENT_BYTES = 65536  # используется в adaptor.py при проверке длины строки

def _ensure_dirs() -> None:
    os.makedirs(LEARNING_DIR, exist_ok=True)

def ensure_storage() -> None:
    _ensure_dirs()
    if not os.path.exists(HMAC_KEY_FILE):
        with open(HMAC_KEY_FILE, "w", encoding="ascii") as f:
            f.write(os.urandom(32).hex())

def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _stable_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def _read_key_hex() -> str:
    try:
        with open(HMAC_KEY_FILE, "r", encoding="ascii", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""

def _sign_line(payload: dict, key_hex: str) -> str:
    data = _stable_json(payload).encode("ascii")
    key = bytes.fromhex(key_hex) if key_hex else b""
    return hmac.new(key, data, hashlib.sha256).hexdigest() if key else ""

def _rotate_if_needed(rotation_mb: int) -> None:
    try:
        if rotation_mb and os.path.exists(REPLAY_FILE):
            if os.path.getsize(REPLAY_FILE) > rotation_mb * 1024 * 1024:
                ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
                dst = os.path.join(LEARNING_DIR, f"replay_buffer-{ts}.jsonl.gz")
                with open(REPLAY_FILE, "rb") as src, gzip.open(dst, "wb", compresslevel=6) as gz:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk: break
                        gz.write(chunk)
                open(REPLAY_FILE, "w").close()
    except Exception:
        pass  # best-effort

def append_events(events: List[dict], rotation_mb: int = 10, retention_days: int = 90) -> int:
    """
    Принимает список событий, проставляет ts / event_id / hmac и аппендит в JSONL.
    Возвращает количество принятых событий. Используется adaptor.py (см. его вызовы).
    """
    ensure_storage()
    _rotate_if_needed(int(rotation_mb or 0))
    key_hex = _read_key_hex()
    accepted = 0
    with open(REPLAY_FILE, "a", encoding="ascii") as f:
        for ev in (events or []):
            if not isinstance(ev, dict):
                continue
            payload = dict(ev)
            payload.setdefault("ts", _now_iso())
            payload.setdefault("event_id", str(payload.get("event_id") or uuid.uuid4()))
            payload.pop("hmac", None)
            payload["hmac"] = _sign_line(payload, key_hex)
            line = _stable_json(payload)
            if len(line) > MAX_EVENT_BYTES:
                continue
            try:
                f.write(line + "\n")
                accepted += 1
            except Exception:
                break
    return accepted
