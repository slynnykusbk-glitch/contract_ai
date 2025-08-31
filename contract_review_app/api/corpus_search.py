from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Generator

from contract_review_app.corpus.db import SessionLocal
from contract_review_app.retrieval.search import search_corpus


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
    mode: str = "bm25",
    session: Session = Depends(get_session),
):
    rows = search_corpus(
        session,
        q,
        mode=mode,
        jurisdiction=jurisdiction,
        source=source,
        act_code=act_code,
        section_code=section_code,
        top=top,
    )
    return {"results": rows}
