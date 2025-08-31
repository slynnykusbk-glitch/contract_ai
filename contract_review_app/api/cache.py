from threading import RLock
from typing import Optional, Dict, Any


class IdempotencyCache:
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._lock = RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


IDEMPOTENCY_CACHE = IdempotencyCache()
