from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from .models import FindingV2, ENGINE_VERSION
from .types import RuleFormat, RuleSource
from .vm import RuleVM
from .yaml_schema import RuleYaml


def discover(root: Path) -> List[RuleSource]:
    root_path = Path(root)
    file_map: Dict[Tuple[str, str], Dict[str, Path]] = {}
    for path in root_path.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".yaml"}:
            continue
        base = path.with_suffix("")
        key = (str(base), path.parent.name)
        entry = file_map.setdefault(key, {})
        entry["py" if path.suffix == ".py" else "yaml"] = path
    sources: List[RuleSource] = []
    for (base, pack), files in sorted(file_map.items()):
        yaml_file = files.get("yaml")
        py_file = files.get("py")
        py_ref = None
        if yaml_file:
            raw_yaml = yaml_file.read_text(encoding="utf-8").replace(":{", ": {")
            try:
                data = yaml.safe_load(raw_yaml) or {}
                ref = data.get("python")
                if isinstance(ref, str) and ref.strip():
                    py_ref = yaml_file.parent / ref.strip()
            except Exception:
                py_ref = None
        if py_file and yaml_file:
            valid_yaml = bool(data and isinstance(data, dict) and data.get("id") and data.get("pack"))
            if py_ref or valid_yaml:
                sources.append(
                    RuleSource(
                        id=Path(base).name,
                        pack=pack,
                        format=RuleFormat.HYBRID,
                        path=yaml_file,
                        py_path=py_ref or py_file,
                        yaml_path=yaml_file,
                    )
                )
            else:
                sources.append(
                    RuleSource(
                        id=Path(base).name,
                        pack=pack,
                        format=RuleFormat.PYTHON,
                        path=py_file,
                        py_path=py_file,
                    )
                )
        elif py_file:
            sources.append(
                RuleSource(
                    id=Path(base).name,
                    pack=pack,
                    format=RuleFormat.PYTHON,
                    path=py_file,
                    py_path=py_file,
                )
            )
        else:
            fmt = RuleFormat.HYBRID if py_ref else RuleFormat.YAML
            sources.append(
                RuleSource(
                    id=Path(base).name,
                    pack=pack,
                    format=fmt,
                    path=yaml_file,
                    py_path=py_ref,
                    yaml_path=yaml_file,
                )
            )
    return sources


def _load_python(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import rule from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def execute(source: RuleSource, context: Dict[str, Any]) -> List[FindingV2]:
    if source.format in {RuleFormat.PYTHON, RuleFormat.HYBRID}:
        module = _load_python(source.py_path or source.path)
        fn = getattr(module, "apply", None) or getattr(module, "rule_main", None)
        if not callable(fn):
            return []
        return fn(context) or []
    if source.format is RuleFormat.YAML:
        raw = source.path.read_text(encoding="utf-8").replace(":{", ": {")
        data = yaml.safe_load(raw)
        rule = RuleYaml.model_validate(data)
        if rule.engine_version != ENGINE_VERSION:
            raise ValueError("engine_version mismatch")
        return RuleVM(rule).evaluate(context)
    raise NotImplementedError(str(source.format))


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
