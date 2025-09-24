import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from contract_review_app.corpus.db import SessionLocal, get_engine, init_db
from contract_review_app.corpus.repo import Repo
from contract_review_app.retrieval.cache import ensure_vector_cache
from contract_review_app.retrieval.config import load_config
from contract_review_app.retrieval.embedder import HashingEmbedder
from contract_review_app.retrieval.indexer import rebuild_index


@pytest.fixture
def session(tmp_path):
    dsn = f"sqlite:///{tmp_path/'retr.db'}"
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    session = SessionLocal()
    repo = Repo(session)
    demo_dir = Path("data/corpus_demo")
    for p in demo_dir.glob("*.yaml"):
        with open(p, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            for item in data["items"]:
                repo.upsert(item)
    rebuild_index(session)
    yield session
    session.close()


def test_load_config_env_override(tmp_path, monkeypatch):
    cfg_path = tmp_path / "retrieval.yaml"
    cfg_path.write_text(
        "vector:\n  embedding_dim: 128\n  embedding_version: v1\n  cache_dir: cache\n"
        "fusion:\n  method: rrf\n  weights:\n    vector: 0.1\n    bm25: 0.9\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("RETRIEVAL_CONFIG", str(cfg_path))
    monkeypatch.setenv("RETRIEVAL_EMBEDDING_DIM", "64")
    monkeypatch.setenv("RETRIEVAL_FUSION_METHOD", "weighted")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_VECTOR", "0.7")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_BM25", "0.3")
    cfg = load_config()
    assert cfg["vector"]["embedding_dim"] == 64
    assert cfg["vector"]["embedding_version"] == "v1"
    assert cfg["fusion"]["method"] == "weighted"
    assert cfg["fusion"]["weights"]["vector"] == 0.7
    assert cfg["fusion"]["weights"]["bm25"] == 0.3


def test_vector_cache_build_and_reuse(session, tmp_path):
    cache_dir = tmp_path / "cache"
    embedder = HashingEmbedder(128)
    vecs, ids, metas, from_cache = ensure_vector_cache(
        session,
        embedder=embedder,
        cache_dir=str(cache_dir),
        emb_ver="emb-dev-1",
    )
    assert not from_cache
    assert len(ids) > 0
    vecs2, ids2, metas2, from_cache2 = ensure_vector_cache(
        session,
        embedder=embedder,
        cache_dir=str(cache_dir),
        emb_ver="emb-dev-1",
    )
    assert from_cache2
    assert vecs.shape == vecs2.shape
    assert np.allclose(vecs, vecs2)
    assert np.array_equal(ids, ids2)
    assert metas == metas2


def test_vector_cache_invalidation_on_version(session, tmp_path):
    cache_dir = tmp_path / "cache"
    embedder = HashingEmbedder(128)
    vecs, ids, metas, from_cache = ensure_vector_cache(
        session,
        embedder=embedder,
        cache_dir=str(cache_dir),
        emb_ver="v1",
    )
    assert not from_cache
    vecs2, ids2, metas2, from_cache2 = ensure_vector_cache(
        session,
        embedder=embedder,
        cache_dir=str(cache_dir),
        emb_ver="v2",
    )
    assert not from_cache2
    assert vecs2.shape == vecs.shape
    files = list(cache_dir.glob("*.npz"))
    assert len(files) == 2
