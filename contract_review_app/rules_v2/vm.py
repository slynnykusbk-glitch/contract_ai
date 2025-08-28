from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from .models import ENGINE_VERSION, FindingV2
from .yaml_schema import RuleYaml


def _get_path(data: Dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    value: Any = data
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def eval_cond(expr: str | bool, context: Dict[str, Any]) -> bool:
    if isinstance(expr, bool):
        return expr

    expr = expr.strip()

    m = re.fullmatch(r"len\((context\.[^)]+)\)\s*>\s*(\d+)", expr)
    if m:
        val = _get_path(context, m.group(1)[len("context.") :])
        try:
            return len(val) > int(m.group(2))
        except Exception:
            return False

    m = re.fullmatch(r"(context\.[^ ]+)\s+contains\s+'([^']*)'", expr)
    if m:
        val = _get_path(context, m.group(1)[len("context.") :])
        return isinstance(val, str) and m.group(2) in val

    m = re.fullmatch(r"(context\.[^ ]+)\s*(==|!=)\s*'([^']*)'", expr)
    if m:
        val = _get_path(context, m.group(1)[len("context.") :])
        if m.group(2) == "==":
            return val == m.group(3)
        return val != m.group(3)

    if expr.startswith("context."):
        val = _get_path(context, expr[len("context.") :])
        return bool(val)

    raise ValueError(f"Unsupported expression: {expr}")


def _merge(*lists: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for lst in lists:
        for item in lst or []:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result


class RuleVM:
    def __init__(self, rule: RuleYaml) -> None:
        self.rule = rule

    def evaluate(self, context: Dict[str, Any]) -> List[FindingV2]:
        findings: List[FindingV2] = []
        for check in self.rule.checks:
            cond = eval_cond(check.when, context)
            if cond and check.any_of:
                cond = cond and any(eval_cond(expr, context) for expr in check.any_of)
            if cond and check.all_of:
                cond = cond and all(eval_cond(expr, context) for expr in check.all_of)
            if cond:
                produce = check.produce or {}
                evidence = _merge(self.rule.evidence, getattr(produce, "evidence", []))
                citation = _merge(self.rule.citation, getattr(produce, "citation", []))
                flags = _merge(self.rule.flags, getattr(produce, "flags", []))
                findings.append(
                    FindingV2(
                        id=self.rule.id,
                        pack=self.rule.pack,
                        severity=self.rule.severity,
                        category=self.rule.category,
                        title=self.rule.title,
                        message=self.rule.message,
                        explain=self.rule.explain,
                        suggestion=self.rule.suggestion,
                        evidence=evidence,
                        citation=citation,
                        flags=flags,
                        version=self.rule.version,
                        engine_version=ENGINE_VERSION,
                        created_at=datetime.now(timezone.utc),
                    )
                )
        return findings
