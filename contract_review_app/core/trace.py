from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
from typing import Any, Dict

from fastapi import Request


class TraceStore:
    """Simple in-memory LRU store for trace snapshots."""

    def __init__(self, maxlen: int = 200, max_size_bytes: int = 0) -> None:
        self.maxlen = maxlen
        self.max_size_bytes = max(0, int(max_size_bytes))
        self._data: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._weights: Dict[str, int] = {}
        self._total_weight = 0

    def _estimate_weight(self, value: Any) -> int:
        try:
            return len(json.dumps(value))
        except TypeError:
            try:
                return len(json.dumps(value, default=str))
            except Exception:
                return len(str(value))

    def _drop_lru(self) -> None:
        try:
            cid, _ = self._data.popitem(last=False)
        except KeyError:
            return
        weight = self._weights.pop(cid, 0)
        self._total_weight = max(0, self._total_weight - weight)

    def _record_weight(self, cid: str) -> None:
        entry = self._data.get(cid)
        if entry is None:
            return
        new_weight = self._estimate_weight(entry)
        old_weight = self._weights.get(cid, 0)
        self._weights[cid] = new_weight
        self._total_weight += new_weight - old_weight

    def _enforce_limits(self) -> None:
        while len(self._data) > self.maxlen:
            self._drop_lru()
        if self.max_size_bytes <= 0:
            return
        while self._total_weight > self.max_size_bytes and self._data:
            self._drop_lru()

    def put(self, cid: str, item: Dict[str, Any]) -> None:
        """Insert *item* under *cid* keeping only the latest *maxlen* items."""
        if not cid or not isinstance(item, dict):
            return
        if cid in self._data:
            existing = self._data[cid]
            merged = dict(existing)
            merged.update(item)
            body_existing = existing.get("body") if isinstance(existing.get("body"), dict) else None
            body_new = item.get("body") if isinstance(item.get("body"), dict) else None
            if body_existing or body_new:
                merged_body: Dict[str, Any] = {}
                if isinstance(body_existing, dict):
                    merged_body.update(body_existing)
                if isinstance(body_new, dict):
                    merged_body.update(body_new)
                merged["body"] = merged_body
            self._data[cid] = merged
        else:
            self._data[cid] = dict(item)
        self._data.move_to_end(cid)
        self._record_weight(cid)
        self._enforce_limits()

    def add(self, cid: str, key: str, value: Any) -> None:
        """Attach a ``key``/``value`` pair to the trace body for ``cid``."""
        if not cid or not key:
            return
        entry = self._data.get(cid)
        if entry is None:
            self.put(cid, {"body": {key: value}})
            return
        body = entry.get("body")
        if not isinstance(body, dict):
            body = {}
        body[key] = value
        entry["body"] = body
        self._data.move_to_end(cid)
        self._record_weight(cid)
        self._enforce_limits()

    def get(self, cid: str) -> Dict[str, Any] | None:
        return self._data.get(cid)

    def list(self) -> list[str]:
        return list(self._data.keys())


def compute_cid(request: Request) -> str:
    """Compute deterministic content id for a request.

    POST/PUT/PATCH: path + sorted(query) + canonical JSON body
    GET/DELETE: path + sorted(query)
    """
    path = request.url.path
    query_items = sorted(request.query_params.multi_items())
    query = "&".join(f"{k}={v}" for k, v in query_items)
    body_part = ""
    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        body_bytes = getattr(request.state, "body", b"")
        try:
            obj: Any = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
        except Exception:
            obj = body_bytes.decode("utf-8", "ignore")
        if obj is None:
            body_part = ""
        elif isinstance(obj, (dict, list)):
            body_part = json.dumps(obj, sort_keys=True, ensure_ascii=False)
        else:
            body_part = str(obj)
    raw = f"{path}{query}{body_part}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
