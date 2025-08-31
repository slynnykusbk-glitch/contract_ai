from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Generator

from contract_review_app.corpus.db import SessionLocal
from contract_review_app.retrieval.search import BM25Search


router = APIRouter(prefix="/api/corpus")


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/search")
def corpus_search(
    q: str = Query(..., min_length=1),
    jurisdiction: str | None = None,
    source: str | None = None,
    act_code: str | None = None,
    section_code: str | None = None,
    top: int = 10,
    session: Session = Depends(get_session),
):
    searcher = BM25Search(session)
    rows = searcher.search(
        q,
        jurisdiction=jurisdiction,
        source=source,
        act_code=act_code,
        section_code=section_code,
        top=top,
    )
    results = [
        {
            "id": r["id"],
            "meta": {
                "corpus_id": r["corpus_id"],
                "jurisdiction": r["jurisdiction"],
                "source": r["source"],
                "act_code": r["act_code"],
                "section_code": r["section_code"],
                "version": r["version"],
            },
            "span": {"start": r["start"], "end": r["end"], "lang": r["lang"]},
            "text": r["text"],
            "score": r["score"],
        }
        for r in rows
    ]
    return {"results": results}
