from collections import OrderedDict
import time


class TTLCache:
    def __init__(self, max_items=128, ttl_s=900):
        self.max = max_items
        self.ttl = ttl_s
        self._data = OrderedDict()

    def _purge(self):
        now = time.time()
        keys = [k for k, (v, ts) in self._data.items() if now - ts > self.ttl]
        for k in keys:
            self._data.pop(k, None)
        # LRU trim
        while len(self._data) > self.max:
            self._data.popitem(last=False)

    def get(self, key):
        self._purge()
        if key not in self._data:
            return None
        v, ts = self._data.pop(key)
        self._data[key] = (v, ts)  # refresh LRU
        return v

    def set(self, key, value):
        self._purge()
        if key in self._data:
            self._data.pop(key)
        self._data[key] = (value, time.time())
