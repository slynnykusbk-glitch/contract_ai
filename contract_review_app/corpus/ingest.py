from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

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


def load_dir(dir_path: str) -> List[Dict]:
    items: List[Dict] = []
    for path in sorted(Path(dir_path).glob("*.yaml")):
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if isinstance(data, dict) and "items" in data:
            docs = data["items"]
        else:
            docs = [data]
        for item in docs:
            if not REQUIRED_FIELDS.issubset(item.keys()):
                missing = REQUIRED_FIELDS - set(item.keys())
                raise ValueError(f"{path}: missing fields {missing}")
            items.append(item)
    return items


def to_repo_dto(item: Dict) -> Dict:
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
    dto.update({"text": text, "updated_at": updated_at, "checksum": checksum})
    return dto


def run_ingest(dir_path: str, *, dsn: str | None = None) -> int:
    engine = get_engine(dsn)
    init_db(engine)
    session = SessionLocal()
    repo = Repo(session)
    items = load_dir(dir_path)
    for it in items:
        dto = to_repo_dto(it)
        repo.upsert(dto)
    session.close()
    return len(items)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True)
    p.add_argument("--dsn", default=os.getenv("LEGAL_CORPUS_DSN"))
    args = p.parse_args()
    n = run_ingest(args.dir, dsn=args.dsn)
    print(f"Ingested records: {n}")
