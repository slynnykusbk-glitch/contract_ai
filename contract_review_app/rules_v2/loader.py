from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import re
import yaml


def _preprocess_yaml(raw: str) -> str:
    """Minimal YAML preprocessor.

    The tests supply compact inline mappings like ``key:{ a: 1 }`` which are
    invalid YAML. A light regex normalizes such patterns by inserting a space
    after the colon so that the standard parser can consume the file without
    raising ``ParserError``.
    """
    return re.sub(r":\s*{", ": {", raw)

from .models import FindingV2, ENGINE_VERSION
from .types import RuleFormat, RuleSource
from .vm import RuleVM
from .yaml_schema import RuleYaml


def _preprocess_yaml(raw: str) -> str:
    """Sanitize YAML text before parsing.

    - strip BOM and carriage returns
    - replace tabs with spaces
    - drop ``!!python/*`` tags
    - ensure a space follows ``:`` before ``{`` or ``[``
    """

    s = raw.replace("\ufeff", "")  # remove BOM
    s = s.replace("\r", "")
    s = s.replace("\t", "    ")
    s = re.sub(r"!!python/[^:]+:\s*", "", s)
    s = re.sub(r":\\{", ": {", s)
    s = re.sub(r":\\[", ": [", s)
    return s


# ---------- Discover: no YAML parsing, detect by file presence ----------
def discover(root: Path) -> List[RuleSource]:
    root_path = Path(root)
    file_map: Dict[Tuple[str, str], Dict[str, Path]] = {}

    for path in root_path.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".yaml"}:
            continue
        base = path.with_suffix("")  # same basename for .py / .yaml
        key = (str(base), path.parent.name)
        entry = file_map.setdefault(key, {})
        entry["py" if path.suffix == ".py" else "yaml"] = path

    sources: List[RuleSource] = []
    for (base, pack), files in sorted(file_map.items()):
        name = Path(base).name
        py_file = files.get("py")
        yaml_file = files.get("yaml")

        if py_file and yaml_file:
            # if YAML contains an id -> treat pair as hybrid, otherwise fall back
            # to the Python-only rule.
            has_id = False
            try:
                raw = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(_preprocess_yaml(raw)) or {}
                has_id = bool(data.get("id"))
            except Exception:
                pass
            if has_id:
                sources.append(
                    RuleSource(
                        id=name,
                        pack=pack,
                        format=RuleFormat.HYBRID,
                        path=yaml_file,
                        py_path=py_file,
                        yaml_path=yaml_file,
                    )
                )
            else:
                sources.append(
                    RuleSource(
                        id=name,
                        pack=pack,
                        format=RuleFormat.PYTHON,
                        path=py_file,
                        py_path=py_file,
                        yaml_path=yaml_file,
                    )
                )
        elif py_file:
            sources.append(
                RuleSource(
                    id=name,
                    pack=pack,
                    format=RuleFormat.PYTHON,
                    path=py_file,
                    py_path=py_file,
                )
            )
        else:  # yaml only
            # treat as hybrid if YAML references a python impl via ``python:``
            py_ref = None
            try:
                raw = yaml_file.read_text(encoding="utf-8")
                data = yaml.safe_load(_preprocess_yaml(raw)) or {}
                py_name = data.get("python")
                if isinstance(py_name, str):
                    py_ref = yaml_file.parent / py_name
            except Exception:
                py_ref = None
            if py_ref and py_ref.exists():
                sources.append(
                    RuleSource(
                        id=name,
                        pack=pack,
                        format=RuleFormat.HYBRID,
                        path=yaml_file,  # main spec
                        py_path=py_ref,
                        yaml_path=yaml_file,
                    )
                )
            else:
                sources.append(
                    RuleSource(
                        id=name,
                        pack=pack,
                        format=RuleFormat.YAML,
                        path=yaml_file,  # type: ignore[arg-type]
                        yaml_path=yaml_file,
                    )
                )
    return sources


# ---------- Python rule loader ----------
def _load_python(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import rule from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


# ---------- Coercion helpers for Python rule return values ----------
def _coerce_one(obj: Any) -> FindingV2:
    if isinstance(obj, FindingV2):
        return obj
    if isinstance(obj, dict):
        # pydantic v2 first (model_validate), fallback to constructor
        if hasattr(FindingV2, "model_validate"):
            return FindingV2.model_validate(obj)  # type: ignore[attr-defined]
        return FindingV2(**obj)
    raise TypeError(f"Invalid finding item: {type(obj)!r}")


def _coerce_findings(ret: Any) -> List[FindingV2]:
    if ret is None:
        return []
    items: Iterable[Any] = ret if isinstance(ret, list) else [ret]
    out: List[FindingV2] = []
    for it in items:
        try:
            out.append(_coerce_one(it))
        except Exception:
            # мягкая устойчивость к мусорным элементам во имя обратной совместимости
            continue
    return out


# ---------- Execute ----------
def execute(source: RuleSource, context: Dict[str, Any]) -> List[FindingV2]:
    if source.format in {RuleFormat.PYTHON, RuleFormat.HYBRID}:
        module = _load_python(source.py_path or source.path)
        fn = getattr(module, "apply", None) or getattr(module, "rule_main", None)
        if not callable(fn):
            return []
        ret = fn(context)
        return _coerce_findings(ret)

    if source.format is RuleFormat.YAML:
        raw = source.path.read_text(encoding="utf-8")
        raw = _preprocess_yaml(raw)
        data = yaml.safe_load(raw)
        rule = RuleYaml.model_validate(data)
        if rule.engine_version != ENGINE_VERSION:
            raise ValueError("engine_version mismatch")
        return RuleVM(rule).evaluate(context)

    raise NotImplementedError(str(source.format))


# ---------- High-level wrapper ----------
class PolicyPackLoader:
    def __init__(self, root: Path):
        self.root = Path(root)
        self._sources: List[RuleSource] = []

    def discover(self) -> List[RuleSource]:
        self._sources = discover(self.root)
        return self._sources

    def execute(self, source: RuleSource | List[RuleSource], context: Dict[str, Any]) -> List[FindingV2]:
        if isinstance(source, list):
            findings: List[FindingV2] = []
            for s in source:
                findings.extend(execute(s, context))
            return findings
        return execute(source, context)

    def run_all(self, context: Dict[str, Any]) -> List[FindingV2]:
        findings: List[FindingV2] = []
        for src in (self._sources or self.discover()):
            findings.extend(execute(src, context))
        return findings
