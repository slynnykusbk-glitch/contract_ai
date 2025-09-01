from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import Generator, List

from contract_review_app.corpus.db import SessionLocal
from contract_review_app.retrieval.search import search_corpus

from .limits import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from .models import CorpusSearchRequest, CorpusSearchResponse, SearchHit, Span, Paging


router = APIRouter(prefix="/api/corpus")


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/search", response_model=CorpusSearchResponse)
def corpus_search(
    body: CorpusSearchRequest,
    request: Request,
    session: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
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

    if "page" in request.query_params or "page_size" in request.query_params:
        total = len(hits)
        start = (page - 1) * page_size
        end = page * page_size
        items = hits[start:end]
        pages = (total + page_size - 1) // page_size
        paging = Paging(page=page, page_size=page_size, total=total, pages=pages)
        return CorpusSearchResponse(hits=items, paging=paging)

    return CorpusSearchResponse(hits=hits, paging=None)
