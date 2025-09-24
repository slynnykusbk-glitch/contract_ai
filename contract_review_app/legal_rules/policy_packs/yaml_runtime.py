from __future__ import annotations
import re
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: str
    tags: List[str] = field(default_factory=list)
    span: Dict[str, int] = field(default_factory=dict)
    captures: Dict[str, Any] = field(default_factory=dict)
    advice: Optional[str] = None


@dataclass
class Rule:
    id: str
    title: str
    severity: str
    tags: List[str]
    patterns: List[re.Pattern]
    advice: Optional[str] = None
    extractors: Dict[str, re.Pattern] = field(default_factory=dict)


@dataclass
class Pack:
    pack_id: str
    language: str
    jurisdiction: str
    rules: List[Rule]


def _compile_regex(rx: str) -> re.Pattern:
    return re.compile(rx, re.IGNORECASE | re.MULTILINE | re.DOTALL)


def load_pack(path: str | pathlib.Path) -> Pack:
    data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    compiled_rules: List[Rule] = []
    for r in data.get("rules", []):
        pats = []
        for cond in (r.get("when", {}) or {}).get("any", []):
            if "regex" in cond:
                pats.append(_compile_regex(cond["regex"]))
        extracts: Dict[str, re.Pattern] = {}
        for k, v in (r.get("extract") or {}).items():
            extracts[k] = _compile_regex(v["regex"])
        compiled_rules.append(
            Rule(
                id=r["id"],
                title=r["title"],
                severity=str(r.get("severity", "low")).lower(),
                tags=[*r.get("tags", [])],
                patterns=pats,
                advice=r.get("advice"),
                extractors=extracts,
            )
        )
    return Pack(
        pack_id=data.get("pack_id", "pack"),
        language=data.get("language", "en"),
        jurisdiction=data.get("jurisdiction", ""),
        rules=compiled_rules,
    )


def evaluate(text: str, pack: Pack) -> List[Finding]:
    findings: List[Finding] = []
    for rule in pack.rules:
        for pat in rule.patterns:
            m = pat.search(text or "")
            if not m:
                continue
            start = m.start()
            end = m.end()
            caps: Dict[str, Any] = {}
            for name, rx in rule.extractors.items():
                em = rx.search(text or "")
                if em:
                    caps[name] = em.group(1) if em.groups() else em.group(0)
            findings.append(
                Finding(
                    rule_id=rule.id,
                    title=rule.title,
                    severity=rule.severity,
                    tags=list(rule.tags),
                    span={"start": int(start), "length": int(end - start)},
                    captures=caps,
                    advice=rule.advice,
                )
            )
            break  # one hit is enough per rule in MVP
    return findings
