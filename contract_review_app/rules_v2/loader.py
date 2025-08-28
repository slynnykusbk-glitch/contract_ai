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
=======
# contract_review_app/rules_v2/loader.py
"""Policy pack loader for rules v2."""
from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Any, Dict, List

from .models import FindingV2
from .types import LoadedRule

__all__ = ["PolicyPackLoader"]


class PolicyPackLoader:
    """Discover and execute rules for packs."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def discover(self) -> List[LoadedRule]:
        rules: List[LoadedRule] = []
        for pack_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            pack = pack_dir.name
            yaml_files = {p.stem: p for p in pack_dir.glob("*.yaml")}
            py_files = {p.stem: p for p in pack_dir.glob("*.py")}
            for rule_id in sorted(set(yaml_files) | set(py_files)):
                y_path = yaml_files.get(rule_id)
                p_path = py_files.get(rule_id)
                if y_path:
                    py_ref = _extract_python_reference(y_path)
                    if py_ref:
                        rules.append(
                            LoadedRule(
                                fmt="hybrid",
                                pack=pack,
                                rule_id=rule_id,
                                impl=py_ref,
                                path=y_path,
                            )
                        )
                        continue
                if p_path:
                    rules.append(
                        LoadedRule(
                            fmt="python",
                            pack=pack,
                            rule_id=rule_id,
                            impl=p_path,
                            path=p_path,
                        )
                    )
                elif y_path:
                    rules.append(
                        LoadedRule(
                            fmt="yaml",
                            pack=pack,
                            rule_id=rule_id,
                            impl=None,
                            path=y_path,
                        )
                    )
        return rules

    def execute(self, rules: List[LoadedRule], ctx: Dict[str, Any]) -> List[FindingV2]:
        findings: List[FindingV2] = []
        for rule in rules:
            if rule.fmt == "yaml":
                raise NotImplementedError(
                    f"YAML-only rule execution not implemented for {rule.pack}/{rule.rule_id}"
                )
            py_path = Path(rule.impl)
            module_name = f"{rule.pack}_{rule.rule_id}".replace("-", "_")
            loader = SourceFileLoader(module_name, str(py_path))
            spec = importlib.util.spec_from_loader(module_name, loader)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module {module_name}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            rule_main = getattr(module, "rule_main")
            result = rule_main(ctx)
            if not isinstance(result, list):
                raise TypeError("rule_main must return a list")
            for item in result:
                if isinstance(item, FindingV2):
                    findings.append(item)
                elif isinstance(item, dict):
                    findings.append(FindingV2(**item))
                else:
                    raise TypeError(f"Unsupported finding type: {type(item)!r}")
        return findings


def _extract_python_reference(yaml_path: Path) -> Path | None:
    try:
        text = yaml_path.read_text(encoding="utf-8")
    except Exception:
        return None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("python:"):
            ref = s.split(":", 1)[1].strip().strip('"').strip("'")
            return (yaml_path.parent / ref).resolve()
    return None
