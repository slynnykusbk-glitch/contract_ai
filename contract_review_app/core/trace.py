from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict


class TraceStore:
    """Simple in-memory LRU store for trace snapshots."""

    def __init__(self, maxlen: int = 200) -> None:
        self.maxlen = maxlen
        self._data: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    def put(self, cid: str, item: Dict[str, Any]) -> None:
        """Insert *item* under *cid* keeping only the latest *maxlen* items."""
        if not cid:
            return
        if cid in self._data:
            self._data.move_to_end(cid)
        self._data[cid] = item
        while len(self._data) > self.maxlen:
            self._data.popitem(last=False)

    def get(self, cid: str) -> Dict[str, Any] | None:
        return self._data.get(cid)

    def list(self) -> list[str]:
        return list(self._data.keys())
