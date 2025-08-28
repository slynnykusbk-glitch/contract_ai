import importlib.util as _util
import importlib.machinery as _machinery

_loader = _machinery.SourceFileLoader('dataclasses', '/usr/lib/python3.12/dataclasses.py')
_spec = _util.spec_from_loader('dataclasses', _loader)
_dataclasses = _util.module_from_spec(_spec)
_loader.exec_module(_dataclasses)

__all__ = _dataclasses.__all__
for _name in __all__:
    globals()[_name] = getattr(_dataclasses, _name)


def asdict(obj, *, dict_factory=dict):  # type: ignore[override]
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    return _dataclasses.asdict(obj, dict_factory=dict_factory)
