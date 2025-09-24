import pytest
import yaml
from pathlib import Path

from contract_review_app.corpus.db import SessionLocal, get_engine, init_db
from contract_review_app.corpus.repo import Repo
from contract_review_app.retrieval.config import load_config
from contract_review_app.retrieval.embedder import HashingEmbedder
from contract_review_app.retrieval.cache import ensure_vector_cache
from contract_review_app.retrieval.indexer import rebuild_index
from contract_review_app.retrieval.search import search_corpus


@pytest.fixture
def session(tmp_path, monkeypatch):
    dsn = f"sqlite:///{tmp_path/'wf.db'}"
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    sess = SessionLocal()
    repo = Repo(sess)
    demo_dir = Path("data/corpus_demo")
    for p in demo_dir.glob("*.yaml"):
        with open(p, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            for item in data["items"]:
                repo.upsert(item)
    rebuild_index(sess)
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("RETRIEVAL_CACHE_DIR", str(cache_dir))
    cfg = load_config()
    embedder = HashingEmbedder(cfg["vector"]["embedding_dim"])
    ensure_vector_cache(
        sess,
        embedder=embedder,
        cache_dir=cfg["vector"]["cache_dir"],
        emb_ver=cfg["vector"]["embedding_version"],
    )
    yield sess
    sess.close()


def test_weighted_equals_vector_when_vector_weight_1(session, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_FUSION_METHOD", "weighted")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_VECTOR", "1.0")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_BM25", "0.0")
    vec = search_corpus(session, "processing", mode="vector", top=5)
    hybrid = search_corpus(session, "processing", mode="hybrid", top=5)
    assert [r["id"] for r in hybrid] == [r["id"] for r in vec]


def test_weighted_equals_bm25_when_bm25_weight_1(session, monkeypatch):
    monkeypatch.setenv("RETRIEVAL_FUSION_METHOD", "weighted")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_VECTOR", "0.0")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_BM25", "1.0")
    bm = search_corpus(session, "processing", mode="bm25", top=5)
    hybrid = search_corpus(session, "processing", mode="hybrid", top=5)
    assert [r["id"] for r in hybrid] == [r["id"] for r in bm]
