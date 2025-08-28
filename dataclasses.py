"""Shim module that proxies to the standard library ``dataclasses``.

Provides a compatibility layer so objects exposing ``model_dump`` (e.g.
Pydantic models) can be passed to ``asdict``. The real stdlib module is
loaded dynamically using :func:`importlib.import_module` without relying on
hard-coded filesystem paths.
"""

import sys
from importlib import import_module

_this_module = sys.modules[__name__]
_path0 = sys.path.pop(0)
try:
    sys.modules.pop(__name__, None)
    _dataclasses = import_module("dataclasses")
finally:
    sys.path.insert(0, _path0)
    sys.modules[__name__] = _this_module

__all__ = _dataclasses.__all__
for _name in __all__:
    globals()[_name] = getattr(_dataclasses, _name)


def asdict(obj, *, dict_factory=dict):  # type: ignore[override]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return _dataclasses.asdict(obj, dict_factory=dict_factory)
