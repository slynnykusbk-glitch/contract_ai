# ASCII-only
"""
Learning adaptor: local, deterministic template re-ranking.
Public API (stable):
  - get_config() -> dict
  - log_event(event: dict) -> None
  - update_weights(min_events: int | None = None) -> dict
  - rank_templates(clause_type: str, context: dict) -> list[dict]

This module relies on learning storage created by replay_io.ensure_storage()
and events appended via replay_io.append_events([...]).
"""

import os
import io
import json
import time
import gzip
import hmac
import math
import uuid
import errno
import hashlib
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

# Use the replay_io storage and constants
from . import replay_io as rio

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # contract_review_app/
LEARNING_DIR = os.path.join(BASE_DIR, "learning")
WEIGHTS_DIR = os.path.join(LEARNING_DIR, "weights")
WEIGHTS_FILE = os.path.join(WEIGHTS_DIR, "weights.json")
WEIGHTS_LOCK = os.path.join(LEARNING_DIR, ".weights.lock")

# Defaults / knobs
CFG_VERSION = "1"
CFG_ENABLED = True
CFG_RETENTION_DAYS = int(os.getenv("LEARNING_RETENTION_DAYS", "90"))
CFG_ROTATION_MB = int(os.getenv("LEARNING_ROTATION_MB", "10"))
CFG_UPDATE_MIN_EVENTS = int(os.getenv("LEARNING_UPDATE_MIN_EVENTS", "50"))

# Learning math knobs
LAPLACE_ALPHA = 1.0           # smoothing for counts
EWMA_LAMBDA = 0.2             # recency emphasis
QUALITY_BONUS_RISK = 0.02     # bonus if risk_ord decreased
QUALITY_BONUS_SCORE = 0.01    # bonus if score_delta > 0
MAX_DELTA_FROM_BASE = 0.25    # clamp influence in pipeline (documented here for reference)

# Segment key fields (keep order stable!)
SEGMENT_FIELDS = ("clause_type", "mode", "jurisdiction", "contract_type", "user_role")

_lock_guard = threading.Lock()

# ----------------------- helpers -----------------------

def _ensure_dirs():
    os.makedirs(LEARNING_DIR, exist_ok=True)
    os.makedirs(WEIGHTS_DIR, exist_ok=True)

def _read_hex(path: str) -> str:
    with open(path, "r", encoding="ascii", errors="ignore") as f:
        return f.read().strip()

def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _parse_iso(ts: str) -> datetime:
    # Accept "YYYY-MM-DDTHH:MM:SSZ"
    if not ts:
        return datetime.utcfromtimestamp(0)
    s = ts.strip().rstrip("Z")
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        # Fallback
        return datetime.utcfromtimestamp(0)

def _atomic_write_json(path: str, obj: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii") as f:
        json.dump(obj, f, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    os.replace(tmp, path)

def _with_weights_lock(timeout_ms: int = 1000):
    t0 = time.time()
    while True:
        try:
            fd = os.open(WEIGHTS_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return
        except FileExistsError:
            if (time.time() - t0) * 1000 > timeout_ms:
                # stale?
                try:
                    if time.time() - os.path.getmtime(WEIGHTS_LOCK) > 30:
                        os.remove(WEIGHTS_LOCK)
                        continue
                except Exception:
                    pass
                raise TimeoutError("weights lock busy")
            time.sleep(0.01)

def _unlock_weights():
    try:
        os.remove(WEIGHTS_LOCK)
    except FileNotFoundError:
        pass
    except Exception:
        pass

def _verify_hmac(line_obj: dict, key_hex: str) -> bool:
    if "hmac" not in line_obj:
        return False
    provided = str(line_obj.get("hmac"))
    payload = dict(line_obj)
    payload.pop("hmac", None)
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    key = bytes.fromhex(key_hex.strip())
    calc = hmac.new(key, data.encode("ascii"), hashlib.sha256).hexdigest()
    # constant-time compare
    return hmac.compare_digest(provided, calc)

def _segment_key_from_event(e: dict) -> str:
    # tuple-like stable key string
    vals = []
    ctx = e.get("context") or {}
    for f in SEGMENT_FIELDS:
        if f in ("clause_type", "mode"):
            vals.append(str(e.get(f, "")))
        else:
            vals.append(str(ctx.get(f, "")) if isinstance(ctx, dict) else "")
    return "(" + "|".join(f"{SEGMENT_FIELDS[i]}={vals[i]}" for i in range(len(vals))) + ")"

def _segment_key_from_context(clause_type: str, context: dict) -> str:
    vals = []
    for f in SEGMENT_FIELDS:
        if f == "clause_type":
            vals.append(str(clause_type or ""))
        elif f == "mode":
            vals.append(str(context.get("mode", "")) if isinstance(context, dict) else "")
        else:
            vals.append(str(context.get(f, "")) if isinstance(context, dict) else "")
    return "(" + "|".join(f"{SEGMENT_FIELDS[i]}={vals[i]}" for i in range(len(vals))) + ")"

def _default_weights_obj() -> dict:
    return {
        "version": CFG_VERSION,
        "updated": _now_iso(),
        "watermark": {"last_event_ts": "", "last_event_id": ""},
        "by_segment": {}
    }

def _load_weights() -> dict:
    if not os.path.exists(WEIGHTS_FILE):
        return _default_weights_obj()
    try:
        with open(WEIGHTS_FILE, "r", encoding="ascii", errors="ignore") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return _default_weights_obj()
            return data
    except Exception:
        return _default_weights_obj()

# ----------------------- public API -----------------------

def get_config() -> dict:
    """
    Returns current learning config snapshot.
    """
    _ensure_dirs()
    return {
        "enabled": bool(CFG_ENABLED),
        "retention_days": int(CFG_RETENTION_DAYS),
        "rotation_mb": int(CFG_ROTATION_MB),
        "update_min_events": int(CFG_UPDATE_MIN_EVENTS),
        "version": str(CFG_VERSION),
    }

def log_event(event: dict) -> None:
    """
    Append a single event using replay_io (which handles dedup, HMAC, rotation).
    """
    if not isinstance(event, dict):
        return
    rio.ensure_storage()
    # Single-item batch append; ignore result (API is fire-and-forget)
    try:
        rio.append_events([event], rotation_mb=CFG_ROTATION_MB, retention_days=CFG_RETENTION_DAYS)
    except Exception:
        # Do not raise to caller; learning is best-effort
        return

def update_weights(min_events: int | None = None) -> dict:
    """
    Stream new events since watermark, aggregate counts and update weights.json atomically.
    Laplace smoothing + EWMA; small quality bonus; stable structure.
    Returns: {"updated": iso, "events_used": N, "template_count": M}
    """
    rio.ensure_storage()
    _ensure_dirs()
    min_required = int(min_events) if isinstance(min_events, int) else int(CFG_UPDATE_MIN_EVENTS)

    weights = _load_weights()
    by_segment: Dict[str, Dict[str, Dict[str, Any]]] = weights.get("by_segment") or {}

    # Watermark
    last_ts_iso = (weights.get("watermark") or {}).get("last_event_ts", "")
    last_id = (weights.get("watermark") or {}).get("last_event_id", "")
    last_ts = _parse_iso(last_ts_iso)
    used = 0

    # HMAC key
    try:
        key_hex = _read_hex(rio.HMAC_KEY_FILE)
    except Exception:
        key_hex = ""

    # Retention cutoff (ignore very old lines)
    cutoff_dt = datetime.utcnow() - timedelta(days=CFG_RETENTION_DAYS)

    # Aggregate new events
    # counters[(segment_key, template_id)] = {"applied":int,"rejected":int,"risk_improved":int,"score_gain":float,"n":int,"last":iso}
    counters: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def _bump(seg: str, tpl: str, field: str, inc: float = 1.0):
        key = (seg, tpl)
        o = counters.get(key)
        if not o:
            o = {"applied": 0, "rejected": 0, "risk_improved": 0, "score_gain": 0.0, "n": 0, "last": ""}
            counters[key] = o
        o[field] = o.get(field, 0) + inc
        return o

    # Iterate replay buffer (only current file; archives are ignored by design)
    if os.path.exists(rio.REPLAY_FILE):
        with open(rio.REPLAY_FILE, "r", encoding="ascii", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Quick guard against oversized/corrupt lines
                if len(line) > rio.MAX_EVENT_BYTES * 2:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                # Verify HMAC if possible
                try:
                    if key_hex and not _verify_hmac(e, key_hex):
                        continue
                except Exception:
                    continue

                ts_iso = str(e.get("ts", ""))
                ts_dt = _parse_iso(ts_iso)
                if ts_dt < cutoff_dt:
                    continue

                # Watermark filter: process only newer than last_ts (or equal ts with different id)
                if last_ts_iso:
                    if ts_dt < last_ts:
                        continue
                    if ts_dt == last_ts and str(e.get("event_id", "")) == str(last_id):
                        # same event already processed
                        continue

                # Minimal required fields
                if not e.get("clause_type") or not e.get("template_id"):
                    continue

                seg_key = _segment_key_from_event(e)
                tpl_id = str(e.get("template_id"))
                action = str(e.get("action", ""))
                o = _bump(seg_key, tpl_id, "n", 1.0)
                o["last"] = ts_iso

                if action == "applied" or action == "accepted_all":
                    _bump(seg_key, tpl_id, "applied", 1.0)
                elif action == "rejected" or action == "rejected_all":
                    _bump(seg_key, tpl_id, "rejected", 1.0)

                vs = e.get("verdict_snapshot") or {}
                try:
                    ro_from = int(vs.get("risk_ord_from", 0))
                    ro_to = int(vs.get("risk_ord_to", 0))
                    if ro_to < ro_from:
                        _bump(seg_key, tpl_id, "risk_improved", 1.0)
                except Exception:
                    pass
                try:
                    sd = float(vs.get("score_delta", 0.0))
                    if sd > 0:
                        _bump(seg_key, tpl_id, "score_gain", sd)
                except Exception:
                    pass

                used += 1
                last_ts_iso = ts_iso
                last_id = str(e.get("event_id", last_id))

    # Not enough data: still update watermark to avoid re-processing floods,
    # but do not change per-template scores if used < min_required.
    if used == 0:
        # nothing new, return current metadata
        meta = {
            "updated": weights.get("updated") or _now_iso(),
            "events_used": 0,
            "template_count": sum(len(v or {}) for v in by_segment.values()),
        }
        return meta

    # Prepare new weights object
    new_weights = _load_weights()
    new_by_segment: Dict[str, Dict[str, Dict[str, Any]]] = new_weights.get("by_segment") or {}

    # If not enough new events, we still record watermark and updated time, but keep scores as-is.
    if used < min_required:
        new_weights["updated"] = _now_iso()
        new_weights["watermark"] = {"last_event_ts": last_ts_iso, "last_event_id": last_id}
        _with_weights_lock()
        try:
            _atomic_write_json(WEIGHTS_FILE, new_weights)
        finally:
            _unlock_weights()
        return {"updated": new_weights["updated"], "events_used": used,
                "template_count": sum(len(v or {}) for v in new_by_segment.values())}

    # Apply Laplace + EWMA + quality bonus onto segments affected by counters
    for (seg_key, tpl_id), agg in counters.items():
        seg_map = new_by_segment.get(seg_key)
        if not seg_map:
            seg_map = {}
            new_by_segment[seg_key] = seg_map

        prev = seg_map.get(tpl_id) or {}
        prev_score = float(prev.get("score", 0.5))
        prev_n = int(prev.get("n", 0))

        applied = float(agg.get("applied", 0.0))
        rejected = float(agg.get("rejected", 0.0))
        n = int(agg.get("n", 0))

        # Laplace smoothing over cumulative counts:
        # Combine previous n into counts to stabilize if present
        # We do not know previous applied/rejected split; approximate using prev_score * prev_n
        prev_appr = max(0.0, prev_score * prev_n)
        prev_rej = max(0.0, (1.0 - prev_score) * prev_n)
        A = LAPLACE_ALPHA + prev_appr + applied
        R = LAPLACE_ALPHA + prev_rej + rejected
        denom = max(1e-9, A + R)
        p_raw = A / denom

        # EWMA with prev_score as previous state
        learned = (1.0 - EWMA_LAMBDA) * prev_score + EWMA_LAMBDA * p_raw

        # Quality bonus (clamped)
        bonus = 0.0
        if agg.get("risk_improved", 0.0) > 0.0:
            bonus += QUALITY_BONUS_RISK
        if agg.get("score_gain", 0.0) > 0.0:
            bonus += QUALITY_BONUS_SCORE
        learned = max(0.0, min(1.0, learned + min(0.03, bonus)))

        seg_map[tpl_id] = {
            "score": round(learned, 4),
            "n": int(prev_n + n),
            "trend": _trend_symbol(prev_score, learned),
            "last": agg.get("last", _now_iso()),
        }

    # Persist
    new_weights["by_segment"] = new_by_segment
    new_weights["updated"] = _now_iso()
    new_weights["watermark"] = {"last_event_ts": last_ts_iso, "last_event_id": last_id}

    _with_weights_lock()
    try:
        _atomic_write_json(WEIGHTS_FILE, new_weights)
    finally:
        _unlock_weights()

    return {"updated": new_weights["updated"], "events_used": used,
            "template_count": sum(len(v or {}) for v in new_by_segment.values())}

def _trend_symbol(prev: float, curr: float) -> str:
    try:
        if curr > prev + 1e-6:
            return "+"
        if curr < prev - 1e-6:
            return "-"
        return "="
    except Exception:
        return "="

def rank_templates(clause_type: str, context: dict) -> List[dict]:
    """
    Return learned ranking for templates given (clause_type, context).
    Output: list of {"template_id": str, "score": float, "reason": str}
    If no weights present, returns empty list (caller keeps base order).
    """
    _ensure_dirs()
    weights = _load_weights()
    seg_key = _segment_key_from_context(clause_type or "", context or {})
    seg_map = (weights.get("by_segment") or {}).get(seg_key) or {}
    if not seg_map:
        return []
    # Sort by score desc, tie-breaker template_id asc
    items = sorted(seg_map.items(), key=lambda kv: (-float(kv[1].get("score", 0.0)), str(kv[0])))
    out = []
    for tpl_id, meta in items:
        sc = float(meta.get("score", 0.0))
        n = int(meta.get("n", 0))
        trend = str(meta.get("trend", "="))
        out.append({
            "template_id": tpl_id,
            "score": sc,
            "reason": f"learned score={sc:.3f}, n={n}, trend={trend}"
        })
    return out
