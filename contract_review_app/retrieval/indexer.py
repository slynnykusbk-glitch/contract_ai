from __future__ import annotations

import argparse

from sqlalchemy import delete
from sqlalchemy.orm import Session

from contract_review_app.corpus.repo import Repo
from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from .chunker import chunk_text
from .models import CorpusChunk


def rebuild_index(
    session: Session, *, where_latest: bool = True, limit: int | None = None
) -> int:
    repo = Repo(session)
    docs = repo.list_latest() if where_latest else repo.find()
    if limit is not None:
        docs = docs[:limit]
    count = 0
    with session.begin():
        session.execute(delete(CorpusChunk))
        for doc in docs:
            chunks = chunk_text(doc.text, lang=doc.lang)
            for ch in chunks:
                session.add(
                    CorpusChunk(
                        corpus_id=doc.id,
                        jurisdiction=doc.jurisdiction,
                        source=doc.source,
                        act_code=doc.act_code,
                        section_code=doc.section_code,
                        version=doc.version,
                        start=ch.start,
                        end=ch.end,
                        lang=ch.lang,
                        text=ch.text,
                        token_count=ch.token_count,
                        checksum=ch.checksum,
                    )
                )
                count += 1
    session.commit()
    return count


def _cli() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    engine = get_engine()
    init_db(engine)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:
        n = rebuild_index(session, limit=args.limit)
        print(n)


if __name__ == "__main__":
    _cli()
