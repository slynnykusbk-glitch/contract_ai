from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .models import FindingV2, ENGINE_VERSION
from .types import RuleFormat, RuleSource
from .vm import RuleVM
from .yaml_schema import RuleYaml


def discover(root: Path) -> List[RuleSource]:
    """Discover rule sources under *root*.

    Discovery favors hybrid (py+yaml) over python over yaml.
    """

    root_path = Path(root)
    file_map: Dict[tuple[str, str], Dict[str, Path]] = {}

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".yaml"}:
            continue
        base = path.with_suffix("")
        key = (str(base), path.parent.name)
        entry = file_map.setdefault(key, {})
        if path.suffix == ".py":
            entry["py"] = path
        else:
            entry["yaml"] = path

    sources: List[RuleSource] = []
    for (base, pack), files in sorted(file_map.items()):
        if "py" in files and "yaml" in files:
            sources.append(
                RuleSource(
                    id=Path(base).name,
                    pack=pack,
                    format=RuleFormat.HYBRID,
                    path=files["yaml"],
                    py_path=files["py"],
                    yaml_path=files["yaml"],
                )
            )
        elif "py" in files:
            sources.append(
                RuleSource(
                    id=Path(base).name,
                    pack=pack,
                    format=RuleFormat.PYTHON,
                    path=files["py"],
                    py_path=files["py"],
                )
            )
        else:
            sources.append(
                RuleSource(
                    id=Path(base).name,
                    pack=pack,
                    format=RuleFormat.YAML,
                    path=files["yaml"],
                    yaml_path=files["yaml"],
                )
            )

    return sources


def _load_python(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"Cannot import rule from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def execute(source: RuleSource, context: Dict[str, Any]) -> List[FindingV2]:
    """Execute *source* with given *context*."""

    if source.format in {RuleFormat.PYTHON, RuleFormat.HYBRID}:
        module = _load_python(source.py_path or source.path)
        if not hasattr(module, "apply"):
            return []
        result = module.apply(context)
        return result or []

    if source.format is RuleFormat.YAML:
        data = yaml.safe_load(source.path.read_text())
        rule = RuleYaml.model_validate(data)
        if rule.engine_version != ENGINE_VERSION:
            raise ValueError("engine_version mismatch")
        vm = RuleVM(rule)
        return vm.evaluate(context)

    raise NotImplementedError(source.format)
