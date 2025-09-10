from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, Iterable, List

import logging
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


from .models import FindingV2, ENGINE_VERSION  # noqa: E402
from .types import RuleFormat, RuleSource  # noqa: E402
from .vm import RuleVM  # noqa: E402
from .yaml_schema import RuleYaml  # noqa: E402

ALLOWED_RULE_EXTS = {".yml", ".yaml"}
log = logging.getLogger(__name__)


# ---------- Discover: no YAML parsing, detect by file presence ----------
def discover(root: Path) -> List[RuleSource]:
    root_path = Path(root)
    sources: List[RuleSource] = []
    warned_py = False

    for path in root_path.rglob("*"):
        if not path.is_file() or "_legacy_disabled" in path.parts:
            continue
        suffix = path.suffix.lower()
        if suffix == ".py":
            if not warned_py:
                log.warning("Skipped legacy Python rules (*.py).")
                warned_py = True
            continue
        if suffix not in ALLOWED_RULE_EXTS:
            continue
        name = path.stem
        pack = path.parent.name
        sources.append(
            RuleSource(
                id=name,
                pack=pack,
                format=RuleFormat.YAML,
                path=path,
                yaml_path=path,
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
        data = yaml.safe_load(_preprocess_yaml(raw))
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

    def execute(
        self, source: RuleSource | List[RuleSource], context: Dict[str, Any]
    ) -> List[FindingV2]:
        if isinstance(source, list):
            findings: List[FindingV2] = []
            for s in source:
                findings.extend(execute(s, context))
            return findings
        return execute(source, context)

    def run_all(self, context: Dict[str, Any]) -> List[FindingV2]:
        findings: List[FindingV2] = []
        for src in self._sources or self.discover():
            findings.extend(execute(src, context))
        return findings
