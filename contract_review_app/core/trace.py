from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
from typing import Any, Dict

from fastapi import Request


class TraceStore:
    """Simple in-memory LRU store for trace snapshots."""

    def __init__(
        self,
        maxlen: int = 200,
        max_size_bytes: int = 0,
        max_entry_size_bytes: int = 0,
    ) -> None:
        self.maxlen = maxlen
        self.max_size_bytes = max(0, int(max_size_bytes))
        self.max_entry_size_bytes = max(0, int(max_entry_size_bytes))
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

    def _apply_entry_limit(self, cid: str) -> None:
        if self.max_entry_size_bytes <= 0:
            return
        entry = self._data.get(cid)
        if entry is None:
            return
        weight = self._estimate_weight(entry)
        if weight <= self.max_entry_size_bytes:
            return
        body = entry.get("body")
        if not isinstance(body, dict):
            return

        def _resolve_list(
            container: Dict[str, Any], path: tuple[str, ...]
        ) -> list[Any] | None:
            current: Any = container
            for key in path:
                if not isinstance(current, dict):
                    return None
                current = current.get(key)
                if current is None:
                    return None
            return current if isinstance(current, list) else None

        def _trim_reason_buckets(container: Dict[str, Any]) -> bool:
            dispatch = container.get("dispatch")
            if not isinstance(dispatch, dict):
                return False
            candidates = dispatch.get("candidates")
            if not isinstance(candidates, list):
                return False
            bucket_keys = ("patterns", "amounts", "durations", "law", "jurisdiction")
            for candidate in reversed(candidates):
                if not isinstance(candidate, dict):
                    continue
                reasons = candidate.get("reasons")
                if not isinstance(reasons, list):
                    continue
                for reason in reversed(reasons):
                    if not isinstance(reason, dict):
                        continue
                    for key in bucket_keys:
                        bucket = reason.get(key)
                        if isinstance(bucket, list) and bucket:
                            bucket.pop()
                            return True
            return False

        def _trim_reason_list(container: Dict[str, Any]) -> bool:
            dispatch = container.get("dispatch")
            if not isinstance(dispatch, dict):
                return False
            candidates = dispatch.get("candidates")
            if not isinstance(candidates, list):
                return False
            for candidate in reversed(candidates):
                if not isinstance(candidate, dict):
                    continue
                reasons = candidate.get("reasons")
                if isinstance(reasons, list) and reasons:
                    reasons.pop()
                    return True
            return False

        trim_paths: tuple[tuple[str, ...], ...] = (
            ("dispatch", "candidates"),
            ("features", "segments"),
        )

        trimmed = False
        while weight > self.max_entry_size_bytes:
            changed = False
            for path in trim_paths:
                items = _resolve_list(body, path)
                if not items:
                    continue
                # remove items from the tail to favour earlier entries
                items.pop()
                changed = True
                trimmed = True
                weight = self._estimate_weight(entry)
                if weight <= self.max_entry_size_bytes:
                    break
            if not changed:
                if _trim_reason_buckets(body):
                    changed = True
                    trimmed = True
                    weight = self._estimate_weight(entry)
                    if weight <= self.max_entry_size_bytes:
                        break
                elif _trim_reason_list(body):
                    changed = True
                    trimmed = True
                    weight = self._estimate_weight(entry)
                    if weight <= self.max_entry_size_bytes:
                        break
                else:
                    break

        if trimmed:
            # remove empty containers to avoid noise in the payload
            for path in trim_paths:
                parent: Any = body
                for key in path[:-1]:
                    if not isinstance(parent, dict):
                        parent = None
                        break
                    parent = parent.get(key)
                    if parent is None:
                        break
                if parent is None:
                    continue
                last_key = path[-1]
                if isinstance(parent, dict):
                    value = parent.get(last_key)
                    if isinstance(value, list) and not value:
                        parent[last_key] = []

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
            body_existing = (
                existing.get("body") if isinstance(existing.get("body"), dict) else None
            )
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
        self._apply_entry_limit(cid)
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
        self._apply_entry_limit(cid)
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
