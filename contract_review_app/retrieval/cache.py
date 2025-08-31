from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from contract_review_app.corpus.models import CorpusDoc
from .models import CorpusChunk


def corpus_fingerprint(session: Session) -> str:
    """Return deterministic fingerprint of the latest corpus chunks."""
    q = (
        select(
            CorpusChunk.corpus_id,
            CorpusChunk.jurisdiction,
            CorpusChunk.act_code,
            CorpusChunk.section_code,
            CorpusChunk.version,
            CorpusChunk.checksum,
        )
        .join(CorpusDoc, CorpusDoc.id == CorpusChunk.corpus_id)
        .where(CorpusDoc.latest.is_(True))
        .order_by(CorpusChunk.id)
    )
    h = hashlib.blake2b()
    for row in session.execute(q):
        for col in row:
            h.update(str(col).encode("utf-8"))
            h.update(b"|")
    return h.hexdigest()


def cache_paths(cache_dir: str, fp: str, emb_ver: str) -> Tuple[str, str]:
    base = Path(cache_dir)
    npz_path = base / f"vecs_{fp}_{emb_ver}.npz"
    meta_path = base / f"vecs_{fp}_{emb_ver}.json"
    return str(npz_path), str(meta_path)


def ensure_vector_cache(
    session: Session,
    *,
    embedder,
    cache_dir: str,
    emb_ver: str,
) -> Tuple[np.ndarray, np.ndarray, List[dict], bool]:
    """Ensure vector cache exists and return vectors and metadata.

    Returns ``(vecs, ids, metas, from_cache)`` where ``from_cache`` indicates
    whether data was loaded from an existing cache.
    """

    fp = corpus_fingerprint(session)
    npz_path, meta_path = cache_paths(cache_dir, fp, emb_ver)
    os.makedirs(cache_dir, exist_ok=True)
    if os.path.exists(npz_path) and os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        if (
            meta.get("fingerprint") == fp
            and meta.get("embedding_version") == emb_ver
            and meta.get("dim") == embedder.dim
        ):
            data = np.load(npz_path)
            vecs = data["vecs"].astype(np.float32)
            ids = data["ids"].astype(np.int64)
            metas = meta.get("metas", [])
            return vecs, ids, metas, True
    # rebuild
    q = (
        select(
            CorpusChunk.id,
            CorpusChunk.corpus_id,
            CorpusChunk.jurisdiction,
            CorpusChunk.source,
            CorpusChunk.act_code,
            CorpusChunk.section_code,
            CorpusChunk.version,
            CorpusChunk.start,
            CorpusChunk.end,
            CorpusChunk.lang,
            CorpusChunk.text,
        )
        .join(CorpusDoc, CorpusDoc.id == CorpusChunk.corpus_id)
        .where(CorpusDoc.latest.is_(True))
        .order_by(CorpusChunk.id)
    )
    rows = session.execute(q).all()
    texts = [r.text for r in rows]
    vecs = embedder.embed(texts).astype(np.float32)
    ids = np.array([r.id for r in rows], dtype=np.int64)
    metas = [
        {
            "id": r.id,
            "corpus_id": r.corpus_id,
            "jurisdiction": r.jurisdiction,
            "source": r.source,
            "act_code": r.act_code,
            "section_code": r.section_code,
            "version": r.version,
            "start": r.start,
            "end": r.end,
            "lang": r.lang,
            "text": r.text,
        }
        for r in rows
    ]
    np.savez(npz_path, vecs=vecs, ids=ids)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "fingerprint": fp,
                "embedding_version": emb_ver,
                "dim": int(vecs.shape[1]),
                "metas": metas,
            },
            fh,
        )
    return vecs, ids, metas, False
