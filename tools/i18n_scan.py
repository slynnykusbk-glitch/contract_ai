#!/usr/bin/env python
"""Simple i18n scanner.

Searches for any non-ASCII or Cyrillic characters in given directories.
Exits with code 1 if any such characters are found.

Usage: python tools/i18n_scan.py [PATH ...]
If no paths are provided, defaults to contract_review_app/, word_addin_dev/, core/rules/
The following directory names are ignored anywhere in the path:
  tests/, samples/, docs/, i18n/fixtures/
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")
DEFAULT_PATHS = ["contract_review_app", "word_addin_dev", "core/rules"]
EXCLUDE_PARTS = {"tests", "samples", "docs"}
# special prefix to exclude like i18n/fixtures
EXCLUDE_PREFIXES = [Path("i18n/fixtures")]


def _is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_PARTS:
        return True
    for pref in EXCLUDE_PREFIXES:
        try:
            path.relative_to(pref)
            return True
        except Exception:
            continue
    return False


def _scan_file(path: Path) -> List[Tuple[int, int, str]]:
    issues: List[Tuple[int, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return issues
    for lineno, line in enumerate(text.splitlines(), 1):
        # find first offending char to report; collect all though
        for col, ch in enumerate(line, 1):
            if CYRILLIC_RE.match(ch) or NON_ASCII_RE.match(ch):
                issues.append((lineno, col, ch))
    return issues


def _scan_paths(paths: Iterable[Path]) -> List[str]:
    findings: List[str] = []
    for root in sorted(set(paths)):
        if not root.exists():
            continue
        if root.is_file():
            iterable = [root]
        else:
            iterable = sorted(p for p in root.rglob("*") if p.is_file())
        for file in iterable:
            if _is_excluded(file):
                continue
            issues = _scan_file(file)
            for lineno, col, ch in issues:
                findings.append(f"{file}:{lineno}:{col}:{ch}")
    return findings


def main(argv: List[str]) -> int:
    paths = [Path(p) for p in argv] if argv else [Path(p) for p in DEFAULT_PATHS]
    findings = _scan_paths(paths)
    for line in findings:
        print(line)
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main(sys.argv[1:]))
