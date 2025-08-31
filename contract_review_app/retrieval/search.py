from __future__ import annotations

import re
from typing import List

import numpy as np
from sqlalchemy.orm import Session

from .cache import ensure_vector_cache
from .config import load_config
from .embedder import HashingEmbedder


class BM25Search:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        source: str | None = None,
        act_code: str | None = None,
        section_code: str | None = None,
        top: int = 10,
    ):
        terms = re.findall(r"\w+", query.lower())
        if not terms:
            return []

        def _prefix(t: str) -> str:
            for suf in ("ing", "ed", "es", "s"):
                if t.endswith(suf) and len(t) - len(suf) >= 3:
                    t = t[: -len(suf)]
                    break
            return f"{t}*"

        q = " OR ".join(_prefix(t) for t in terms)
        sql = (
            "SELECT c.id, c.corpus_id, c.start, c.end, c.jurisdiction, c.source, c.act_code, c.section_code, c.version, c.lang, c.text, bm25(corpus_chunks_fts) AS score "
            "FROM corpus_chunks_fts JOIN corpus_chunks c ON c.id = corpus_chunks_fts.rowid "
            "WHERE corpus_chunks_fts MATCH :q"
        )
        params: dict[str, object] = {"q": q, "top": top}
        if jurisdiction:
            sql += " AND c.jurisdiction = :jurisdiction"
            params["jurisdiction"] = jurisdiction
        if source:
            sql += " AND c.source = :source"
            params["source"] = source
        if act_code:
            sql += " AND c.act_code = :act_code"
            params["act_code"] = act_code
        if section_code:
            sql += " AND c.section_code = :section_code"
            params["section_code"] = section_code
        sql += " ORDER BY score LIMIT :top"
        conn = self.session.connection()
        res = conn.exec_driver_sql(sql, params)
        return [dict(r) for r in res.mappings()]


def _format_rows(rows: List[dict]) -> List[dict]:
    return [
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
            "score": float(r["score"]),
        }
        for r in rows
    ]


def _cosine_search(vecs: np.ndarray, metas: List[dict], ids: np.ndarray, query_vec: np.ndarray, top: int) -> List[dict]:
    norms = np.linalg.norm(vecs, axis=1)
    q_norm = np.linalg.norm(query_vec)
    denom = norms * (q_norm if q_norm != 0 else 1)
    denom[denom == 0] = 1.0
    sims = (vecs @ query_vec) / denom
    order = np.argsort(-sims)[:top]
    results: List[dict] = []
    for idx in order:
        m = metas[idx]
        results.append(
            {
                "id": int(ids[idx]),
                "meta": {
                    "corpus_id": m["corpus_id"],
                    "jurisdiction": m["jurisdiction"],
                    "source": m["source"],
                    "act_code": m["act_code"],
                    "section_code": m["section_code"],
                    "version": m["version"],
                },
                "span": {"start": m["start"], "end": m["end"], "lang": m["lang"]},
                "text": m["text"],
                "score": float(sims[idx]),
            }
        )
    return results


def _rrf_merge(lists: List[List[dict]], k: int, top: int) -> List[dict]:
    scores: dict[int, float] = {}
    items: dict[int, dict] = {}
    for lst in lists:
        for rank, item in enumerate(lst, 1):
            i = int(item["id"])
            items.setdefault(i, item)
            scores[i] = scores.get(i, 0.0) + 1.0 / (k + rank)
    merged = []
    for i, item in items.items():
        item = item.copy()
        item["score"] = scores[i]
        merged.append(item)
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:top]


def search_corpus(
    session: Session,
    query: str,
    *,
    mode: str = "bm25",
    jurisdiction: str | None = None,
    source: str | None = None,
    act_code: str | None = None,
    section_code: str | None = None,
    top: int = 10,
) -> List[dict]:
    if mode == "bm25":
        rows = BM25Search(session).search(
            query,
            jurisdiction=jurisdiction,
            source=source,
            act_code=act_code,
            section_code=section_code,
            top=top,
        )
        return _format_rows(rows)

    cfg = load_config()
    vec_cfg = cfg["vector"]
    embedder = HashingEmbedder(vec_cfg["embedding_dim"])
    vecs, ids, metas, _ = ensure_vector_cache(
        session,
        embedder=embedder,
        cache_dir=vec_cfg["cache_dir"],
        emb_ver=vec_cfg["embedding_version"],
    )
    q_vec = embedder.embed([query]).astype(np.float32)[0]
    vec_results = _cosine_search(vecs, metas, ids, q_vec, top)
    if mode == "vector":
        return vec_results
    bm25_rows = BM25Search(session).search(
        query,
        jurisdiction=jurisdiction,
        source=source,
        act_code=act_code,
        section_code=section_code,
        top=cfg["bm25"]["top"],
    )
    bm25_results = _format_rows(bm25_rows)
    return _rrf_merge([vec_results, bm25_results], cfg["fusion"].get("rrf_k", 60), top)
