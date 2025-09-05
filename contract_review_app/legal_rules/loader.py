"""Lightweight YAML rule loader and matcher."""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

PLACEHOLDER_RE = re.compile(r"\[(?:DELETE AS APPROPRIATE|●)\]", re.I)

# ---------------------------------------------------------------------------
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load and compile rules on import
# ---------------------------------------------------------------------------
_RULES: List[Dict[str, Any]] = []
_PACKS: List[Dict[str, Any]] = []


def _compile(patterns: Iterable[str]) -> List[re.Pattern[str]]:
    return [re.compile(p, re.I | re.MULTILINE) for p in patterns if p]


def _compile_universal_rule(spec: Dict[str, Any]) -> Dict[str, Any]:
    triggers: List[re.Pattern[str]] = []
    for cond in spec.get("triggers", {}).get("any", []):
        if isinstance(cond, dict):
            pat = cond.get("regex")
        else:
            pat = cond
        if pat:
            triggers.append(re.compile(pat, re.I | re.MULTILINE))

    # take first finding spec for metadata (message/severity)
    finding_spec: Dict[str, Any] = {}
    for chk in spec.get("checks", []) or []:
        if isinstance(chk, dict) and chk.get("finding"):
            finding_spec = chk.get("finding", {})
            break

    return {
        "id": spec.get("id"),
        "clause_type": (spec.get("scope", {}) or {}).get("clauses", [None])[0],
        "triggers": triggers,
        "advice": (finding_spec.get("suggestion") or {}).get("text")
        or finding_spec.get("message"),
        "severity": finding_spec.get("severity_level"),
        "finding": finding_spec,
    }


def load_rule_packs(packs: Optional[List[str]] = None) -> None:
    """Load YAML rule packs by name. If ``packs`` is None all packs are loaded."""

    _RULES.clear()
    _PACKS.clear()
    base = Path(__file__).resolve().parent / "policy_packs"
    if not base.exists():
        return
    for path in base.glob("**/*.yaml"):
        if packs and path.stem not in packs:
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # pragma: no cover - error path
            log.error("Failed to load %s: %s", path, exc)
            continue

        rules_iter: Iterable[Dict[str, Any]]
        if isinstance(data, dict) and data.get("rule"):
            compiled = _compile_universal_rule(data.get("rule", {}))
            _RULES.append(compiled)
            _PACKS.append(
                {
                    "pack": compiled.get("id", path.stem),
                    "file": str(path.relative_to(base)),
                    "rules_count": 1,
                    "rule_ids": [compiled.get("id", path.stem)],
                }
            )
            continue

        if isinstance(data, dict):
            rules_iter = data.get("rules") or []
        elif isinstance(data, list):
            rules_iter = data
        else:
            rules_iter = []

        rule_ids: List[str] = []
        for raw in rules_iter:
            rule_ids.append(str(raw.get("id")))
            if "patterns" in raw:  # legacy schema
                _RULES.append(
                    {
                        "id": raw.get("id"),
                        "clause_type": raw.get("clause_type"),
                        "severity": raw.get("severity"),
                        "patterns": _compile(raw.get("patterns", [])),
                        "advice": raw.get("advice"),
                    }
                )
            else:  # msa_oilgas schema
                triggers = _compile(raw.get("triggers", {}).get("any", []))
                include = _compile(raw.get("checks", {}).get("must_include", []))
                exclude = _compile(raw.get("checks", {}).get("must_exclude", []))
                _RULES.append(
                    {
                        "id": raw.get("id"),
                        "clause_type": raw.get("clause_type"),
                        "severity": raw.get("severity"),
                        "triggers": triggers,
                        "include": include,
                        "exclude": exclude,
                        "placeholders_forbidden": bool(raw.get("placeholders_forbidden")),
                        "advice": raw.get("intent"),
                    }
                )
        _PACKS.append(
            {
                "pack": path.stem,
                "file": str(path.relative_to(base)),
                "rules_count": len(rule_ids),
                "rule_ids": rule_ids,
            }
        )

    if _PACKS:
        log.info(
            "Loaded rule packs: %s",
            ", ".join(f"{p['pack']}({p['rules_count']})" for p in _PACKS),
        )


# load all packs on import
load_rule_packs()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def discover_rules() -> List[Dict[str, Any]]:
    """Return loaded rules without compiled regex objects."""
    out: List[Dict[str, Any]] = []
    for r in _RULES:
        if r.get("patterns"):
            pats = [p.pattern for p in r.get("patterns", [])]
        else:
            pats = [p.pattern for p in r.get("triggers", [])]
        out.append(
            {
                "id": r.get("id"),
                "clause_type": r.get("clause_type"),
                "severity": r.get("severity"),
                "patterns": pats,
                "advice": r.get("advice"),
            }
        )
    return out


def rules_count() -> int:
    """Return the number of loaded rules."""
    return len(_RULES)


def loaded_packs() -> List[Dict[str, Any]]:
    """Return metadata about loaded rule packs."""
    return list(_PACKS)


def match_text(text: str) -> List[Dict[str, Any]]:
    """Match text against loaded rules and return findings."""
    findings: List[Dict[str, Any]] = []
    if not text:
        return findings
    for r in _RULES:
        if r.get("placeholders_forbidden"):
            for m in PLACEHOLDER_RE.finditer(text):
                findings.append(
                    {
                        "rule_id": r.get("id"),
                        "clause_type": r.get("clause_type"),
                        "severity": r.get("severity"),
                        "start": m.start(),
                        "end": m.end(),
                        "snippet": text[m.start() : m.end()],
                        "advice": r.get("advice"),
                    }
                )
        if r.get("patterns"):
            for pat in r.get("patterns", []):
                for m in pat.finditer(text):
                    findings.append(
                        {
                            "rule_id": r.get("id"),
                            "clause_type": r.get("clause_type"),
                            "severity": r.get("severity"),
                            "start": m.start(),
                            "end": m.end(),
                            "snippet": text[m.start() : m.end()],
                            "advice": r.get("advice"),
                        }
                    )
        else:
            trig_match = None
            for t in r.get("triggers", []):
                m = t.search(text)
                if m:
                    trig_match = m
                    break
            if not trig_match:
                continue
            if any(inc.search(text) is None for inc in r.get("include", [])):
                continue
            if any(exc.search(text) for exc in r.get("exclude", [])):
                continue
            findings.append(
                {
                    "rule_id": r.get("id"),
                    "clause_type": r.get("clause_type"),
                    "severity": r.get("severity"),
                    "start": trig_match.start(),
                    "end": trig_match.end(),
                    "snippet": text[trig_match.start() : trig_match.end()],
                    "advice": r.get("advice"),
                }
            )
    return findings

