from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import yaml

RULE_ROOTS = [
    "contract_review_app/legal_rules/policy_packs",
    "core/rules",
]
ALLOWED_RULE_EXTS = {".yml", ".yaml"}
ROOT_DIR = Path(__file__).resolve().parents[1]


def _resolve(p: str | Path) -> Path:
    p = Path(p)
    if not p.is_absolute():
        p = ROOT_DIR / p
    return p


@dataclass
class Entry:
    path: Path
    sha256: str
    title: Optional[str]


def _gather(roots: Sequence[str | Path]) -> tuple[Dict[str, List[Entry]], List[Path]]:
    rule_map: Dict[str, List[Entry]] = {}
    missing: List[Path] = []
    for root in roots:
        base = _resolve(root)
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_dir():
                continue
            if path.suffix.lower() not in ALLOWED_RULE_EXTS:
                continue
            try:
                docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            for data in docs:
                if not data:
                    continue
                if isinstance(data, dict) and data.get("rule"):
                    rules = [data["rule"]]
                elif isinstance(data, dict) and data.get("rules"):
                    rules = list(data.get("rules") or [])
                elif isinstance(data, list):
                    rules = list(data)
                else:
                    rules = [data] if isinstance(data, dict) else []
                for raw in rules:
                    if not isinstance(raw, dict):
                        continue
                    rid = raw.get("rule_id") or raw.get("id")
                    if not rid:
                        if path not in missing:
                            missing.append(path)
                        continue
                    title = raw.get("Title") or raw.get("title")
                    sha = hashlib.sha256(
                        yaml.safe_dump(raw, sort_keys=True).encode("utf-8")
                    ).hexdigest()
                    rule_map.setdefault(rid, []).append(Entry(path, sha, title))
    return rule_map, missing


def validate(paths: Sequence[str | Path] | None = None) -> None:
    roots = paths or RULE_ROOTS
    rule_map, missing = _gather(roots)
    for p in missing:
        print(f"Rule without rule_id: {p}")
    conflicts: List[tuple[str, List[Entry]]] = []
    duplicates: List[tuple[str, List[Entry]]] = []
    for rid, entries in rule_map.items():
        if len(entries) > 1:
            hashes = {e.sha256 for e in entries}
            if len(hashes) > 1:
                conflicts.append((rid, entries))
            else:
                duplicates.append((rid, entries))
    for rid, entries in duplicates:
        paths = ", ".join(str(e.path) for e in entries)
        print(f"Duplicate rule_id {rid} in: {paths}")
    if conflicts:
        for rid, entries in conflicts:
            paths = ", ".join(str(e.path) for e in entries)
            print(f"Conflicting rule_id {rid} in: {paths}")
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        validate()
    except SystemExit as exc:
        sys.exit(exc.code)
