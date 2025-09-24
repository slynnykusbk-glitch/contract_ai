"""Lint migration coverage for YAML rule packs."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, TextIO

import yaml

try:  # Prefer the canonical configuration if available.
    from contract_review_app.legal_rules.loader import (  # type: ignore
        ALLOWED_RULE_EXTS as DEFAULT_ALLOWED_EXTS,
    )
    from contract_review_app.legal_rules.loader import (  # type: ignore
        RULE_ROOTS as DEFAULT_RULE_ROOTS,
    )
except Exception:  # pragma: no cover - fallback for limited environments.
    DEFAULT_RULE_ROOTS = [
        "contract_review_app/legal_rules",
        "core/rules",
    ]
    DEFAULT_ALLOWED_EXTS = {".yml", ".yaml"}


ROOT_DIR = Path(__file__).resolve().parents[1]
VALID_CHANNELS = {"presence", "substantive", "policy", "drafting", "fixup"}


@dataclass
class RuleRecord:
    rule_id: str
    channel: object
    salience: object
    path: Path


@dataclass
class LintResult:
    total_rules: int
    channel_count: int
    salience_count: int
    missing_channel: List[RuleRecord]
    invalid_channel: List[RuleRecord]
    missing_salience: List[RuleRecord]
    invalid_salience: List[RuleRecord]
    duplicates: Dict[str, List[RuleRecord]]
    missing_rule_id: List[Path]

    @property
    def has_issues(self) -> bool:
        return any(
            [
                self.missing_channel,
                self.invalid_channel,
                self.missing_salience,
                self.invalid_salience,
                self.duplicates,
                self.missing_rule_id,
            ]
        )


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT_DIR / candidate
    return candidate


def _iter_rules(doc: object) -> Iterable[dict]:
    if not doc:
        return []
    if isinstance(doc, dict):
        if isinstance(doc.get("rule"), dict):
            return [doc["rule"]]
        if isinstance(doc.get("rules"), list):
            return [r for r in doc.get("rules", []) if isinstance(r, dict)]
        return [doc]
    if isinstance(doc, list):
        return [item for item in doc if isinstance(item, dict)]
    return []


def _gather_records(
    roots: Sequence[str | Path] | None,
    *,
    allowed_exts: Iterable[str],
) -> tuple[List[RuleRecord], List[Path]]:
    records: List[RuleRecord] = []
    missing: set[Path] = set()
    base_dirs = (
        [_resolve(p) for p in roots]
        if roots
        else [_resolve(p) for p in DEFAULT_RULE_ROOTS]
    )
    for base in base_dirs:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix.lower() not in set(allowed_exts):
                continue
            try:
                docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            for doc in docs:
                for rule in _iter_rules(doc):
                    rule_id = rule.get("rule_id") or rule.get("id")
                    if not rule_id:
                        missing.add(path)
                        continue
                    records.append(
                        RuleRecord(
                            rule_id=rule_id,
                            channel=rule.get("channel"),
                            salience=rule.get("salience"),
                            path=path,
                        )
                    )
    return records, sorted(missing)


def _valid_salience(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0 <= value <= 100
    return False


def lint_rules(roots: Sequence[str | Path] | None = None) -> LintResult:
    records, missing_rule_id = _gather_records(roots, allowed_exts=DEFAULT_ALLOWED_EXTS)
    channel_count = 0
    salience_count = 0
    missing_channel: List[RuleRecord] = []
    invalid_channel: List[RuleRecord] = []
    missing_salience: List[RuleRecord] = []
    invalid_salience: List[RuleRecord] = []
    duplicates: Dict[str, List[RuleRecord]] = {}
    seen: Dict[str, List[RuleRecord]] = {}

    for record in records:
        if record.channel in VALID_CHANNELS:
            channel_count += 1
        elif record.channel is None:
            missing_channel.append(record)
        else:
            invalid_channel.append(record)

        if _valid_salience(record.salience):
            salience_count += 1
        elif record.salience is None:
            missing_salience.append(record)
        else:
            invalid_salience.append(record)

        seen.setdefault(record.rule_id, []).append(record)

    for rule_id, entries in seen.items():
        if len(entries) > 1:
            duplicates[rule_id] = entries

    return LintResult(
        total_rules=len(records),
        channel_count=channel_count,
        salience_count=salience_count,
        missing_channel=missing_channel,
        invalid_channel=invalid_channel,
        missing_salience=missing_salience,
        invalid_salience=invalid_salience,
        duplicates=duplicates,
        missing_rule_id=missing_rule_id,
    )


def _format_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _write_section(stream: TextIO, title: str, items: Iterable[str]) -> None:
    items = list(items)
    if not items:
        return
    stream.write(f"\n{title}:\n")
    for item in items:
        stream.write(f"  - {item}\n")


def render_report(result: LintResult, stream: TextIO) -> None:
    stream.write("Rules lint report\n")
    stream.write("==================\n")
    stream.write(
        f"Total rules: {result.total_rules}\n"
        f"With channel: {result.channel_count}\n"
        f"With salience: {result.salience_count}\n"
    )

    _write_section(
        stream,
        "Missing channel",
        (f"{rec.rule_id} ({_format_path(rec.path)})" for rec in result.missing_channel),
    )
    _write_section(
        stream,
        "Invalid channel",
        (
            f"{rec.rule_id}={rec.channel!r} ({_format_path(rec.path)})"
            for rec in result.invalid_channel
        ),
    )
    _write_section(
        stream,
        "Missing salience",
        (
            f"{rec.rule_id} ({_format_path(rec.path)})"
            for rec in result.missing_salience
        ),
    )
    _write_section(
        stream,
        "Invalid salience",
        (
            f"{rec.rule_id}={rec.salience!r} ({_format_path(rec.path)})"
            for rec in result.invalid_salience
        ),
    )
    _write_section(
        stream,
        "Duplicate rule_id",
        (
            f"{rule_id} -> {', '.join(_format_path(r.path) for r in records)}"
            for rule_id, records in sorted(result.duplicates.items())
        ),
    )
    _write_section(
        stream,
        "Missing rule_id",
        (_format_path(path) for path in result.missing_rule_id),
    )

    if not result.has_issues:
        stream.write("\nNo issues found.\n")


def run(
    roots: Sequence[str | Path] | None = None,
    *,
    strict: bool | None = None,
    stream: TextIO | None = None,
) -> int:
    if stream is None:
        stream = sys.stdout
    if strict is None:
        strict = os.getenv("FEATURE_RULES_LINT_STRICT") == "1"

    result = lint_rules(roots)
    render_report(result, stream)

    return 1 if strict and result.has_issues else 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv or [])
    roots: Sequence[str | Path] | None = argv or None
    return run(roots)


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    sys.exit(main(sys.argv[1:]))
