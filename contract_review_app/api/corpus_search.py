from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Generator, List

from contract_review_app.corpus.db import SessionLocal
from contract_review_app.retrieval.search import search_corpus

from .models import CorpusSearchRequest, CorpusSearchResponse, SearchHit, Span


router = APIRouter(prefix="/api/corpus")


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/search", response_model=CorpusSearchResponse)
def corpus_search(body: CorpusSearchRequest, session: Session = Depends(get_session)):
    rows = search_corpus(
        session,
        body.q,
        mode=body.method,
        jurisdiction=body.jurisdiction,
        source=body.source,
        act_code=body.act_code,
        section_code=body.section_code,
        top=body.k,
    )
    hits: List[dict] = []
    for r in rows:
        hit = SearchHit(
            doc_id=str(r.get("id")),
            score=float(r.get("score", 0.0)),
            span=Span(**r.get("span", {})),
            snippet=r.get("snippet"),
            title=(r.get("meta") or {}).get("title"),
            text=r.get("text"),
            meta=r.get("meta"),
            bm25_score=r.get("bm25_score"),
            cosine_sim=r.get("cosine_sim"),
            rank_fusion=r.get("rank_fusion"),
        ).model_dump()
        hits.append(hit)
    return CorpusSearchResponse(hits=hits)
