from __future__ import annotations

import re
from typing import List

import numpy as np
from sqlalchemy.orm import Session

from .cache import ensure_vector_cache
from .config import load_config
from .embedder import HashingEmbedder
from .fusion import rrf, weighted_fusion
from .highlight import make_snippet


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


def _format_rows(rows: List[dict], query: str) -> List[dict]:
    formatted = []
    for r in rows:
        item = {
            "id": r["id"],
            "meta": {
                "corpus_id": r["corpus_id"],
                "jurisdiction": r["jurisdiction"],
                "source": r["source"],
                "act_code": r["act_code"],
                "section_code": r["section_code"],
                "version": r["version"],
            },
            "span": {"start": r["start"], "end": r["end"]},
            "text": r["text"],
            "snippet": make_snippet(r["text"], query),
            "bm25_score": float(r["score"]),
            "cosine_sim": None,
            "rank_fusion": None,
        }
        item["score"] = item["bm25_score"]
        formatted.append(item)
    return formatted


def _cosine_search(
    vecs: np.ndarray,
    metas: List[dict],
    ids: np.ndarray,
    query_vec: np.ndarray,
    query: str,
    top: int,
) -> List[dict]:
    norms = np.linalg.norm(vecs, axis=1)
    q_norm = np.linalg.norm(query_vec)
    denom = norms * (q_norm if q_norm != 0 else 1)
    denom[denom == 0] = 1.0
    sims = (vecs @ query_vec) / denom
    order = np.argsort(-sims)[:top]
    results: List[dict] = []
    for idx in order:
        m = metas[idx]
        item = {
            "id": int(ids[idx]),
            "meta": {
                "corpus_id": m["corpus_id"],
                "jurisdiction": m["jurisdiction"],
                "source": m["source"],
                "act_code": m["act_code"],
                "section_code": m["section_code"],
                "version": m["version"],
            },
            "span": {"start": m["start"], "end": m["end"]},
            "text": m["text"],
            "snippet": make_snippet(m["text"], query),
            "bm25_score": None,
            "cosine_sim": float(sims[idx]),
            "rank_fusion": None,
        }
        item["score"] = item["cosine_sim"]
        results.append(item)
    return results


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
        return _format_rows(rows, query)

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
    vec_results = _cosine_search(vecs, metas, ids, q_vec, query, top)
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
    bm25_results = _format_rows(bm25_rows, query)

    bm25_ids = [r["id"] for r in bm25_results]
    vec_ids = [r["id"] for r in vec_results]
    k = cfg["fusion"].get("rrf_k", 60)
    if cfg["fusion"].get("method") == "weighted":
        order = weighted_fusion(
            bm25_ids,
            vec_ids,
            cfg["fusion"]["weights"]["bm25"],
            cfg["fusion"]["weights"]["vector"],
            k,
        )
        scores: dict[int, float] = {}
        for rank, i in enumerate(bm25_ids, 1):
            scores[i] = scores.get(i, 0.0) + cfg["fusion"]["weights"]["bm25"] / (
                k + rank
            )
        for rank, i in enumerate(vec_ids, 1):
            scores[i] = scores.get(i, 0.0) + cfg["fusion"]["weights"]["vector"] / (
                k + rank
            )
    else:
        order = rrf(bm25_ids, vec_ids, k)
        scores = {}
        for rank, i in enumerate(bm25_ids, 1):
            scores[i] = scores.get(i, 0.0) + 1.0 / (k + rank)
        for rank, i in enumerate(vec_ids, 1):
            scores[i] = scores.get(i, 0.0) + 1.0 / (k + rank)

    bm25_map = {r["id"]: r for r in bm25_results}
    vec_map = {r["id"]: r for r in vec_results}
    merged: List[dict] = []
    for i in order:
        if scores.get(i, 0.0) <= 0:
            continue
        base = vec_map.get(i, bm25_map.get(i))
        item = {
            "id": i,
            "meta": base["meta"],
            "span": base["span"],
            "text": base["text"],
            "snippet": base["snippet"],
            "bm25_score": bm25_map.get(i, {}).get("bm25_score"),
            "cosine_sim": vec_map.get(i, {}).get("cosine_sim"),
            "rank_fusion": len(merged) + 1,
        }
        item["score"] = scores.get(i, 0.0)
        merged.append(item)
        if len(merged) >= top:
            break

    return merged
