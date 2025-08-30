from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Any

import yaml

from .normalizer import normalize_text, utc_iso, checksum_for
from .db import get_engine, init_db, SessionLocal
from .repo import Repo

REQUIRED_FIELDS = {
    "source",
    "jurisdiction",
    "act_code",
    "act_title",
    "section_code",
    "section_title",
    "version",
    "updated_at",
    "text",
    "rights",
}


def load_dir(dir_path: str) -> List[Dict[str, Any]]:
    """Load all YAML items from ``dir_path``.

    Each ``*.yaml`` file may contain a single object or ``{"items": [...]}``.
    Returns a list of item dictionaries after validating required fields.
    """

    path = Path(dir_path)
    items: List[Dict[str, Any]] = []
    for file in sorted(path.glob("*.yaml")):
        with open(file, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if isinstance(data, dict) and "items" in data:
            objs = data.get("items", []) or []
        else:
            objs = [data]
        for obj in objs:
            missing = [f for f in REQUIRED_FIELDS if f not in obj]
            if missing:
                raise ValueError(f"Missing fields {missing} in {file}")
            items.append(obj)
    return items


def to_repo_dto(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise fields and compute checksum for repository ingestion."""

    text = normalize_text(item["text"])
    updated_at = utc_iso(item["updated_at"])
    checksum = checksum_for(
        item["jurisdiction"],
        item["act_code"],
        item["section_code"],
        item["version"],
        text,
    )
    dto = dict(item)
    dto["text"] = text
    dto["updated_at"] = updated_at
    dto["checksum"] = checksum
    return dto


def run_ingest(dir_path: str, *, dsn: str | None = None) -> int:
    """Ingest YAML files from ``dir_path`` into the corpus database."""

    if dsn is None:
        dsn = os.getenv("LEGAL_CORPUS_DSN")
    if dsn is None:
        local = Path(".local")
        local.mkdir(exist_ok=True)
        dsn = f"sqlite:///{(local / 'corpus.db').resolve()}"

    engine = get_engine(dsn)
    init_db(engine)

    session = SessionLocal(bind=engine)
    repo = Repo(session)

    records = load_dir(dir_path)
    for item in records:
        repo.upsert(to_repo_dto(item))

    session.close()
    return len(records)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True)
    p.add_argument("--dsn", default=os.getenv("LEGAL_CORPUS_DSN"))
    args = p.parse_args()
    n = run_ingest(args.dir, dsn=args.dsn)
    print(f"Ingested records: {n}")
