import yaml
import yaml
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from contract_review_app.corpus.db import SessionLocal, get_engine, init_db
from contract_review_app.corpus.repo import Repo
from contract_review_app.retrieval.cache import ensure_vector_cache
from contract_review_app.retrieval.config import load_config
from contract_review_app.retrieval.embedder import HashingEmbedder
from contract_review_app.retrieval.indexer import rebuild_index
from contract_review_app.api.corpus_search import router


@pytest.fixture
def client(tmp_path, monkeypatch):
    dsn = f"sqlite:///{tmp_path/'api.db'}"
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
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    sess.close()


def test_search_returns_snippet_and_span(client):
    r = client.post(
        "/api/corpus/search",
        json={"q": "principles processing", "method": "hybrid", "k": 5},
    )
    assert r.status_code == 200
    results = r.json()["hits"]
    assert results

    def stem(w: str) -> str:
        for suf in ("ing", "ed", "es", "s"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                return w[: -len(suf)]
        return w

    stems = {stem(w) for w in {"principles", "processing"}}
    for item in results:
        assert isinstance(item.get("snippet"), str) and len(item["snippet"]) > 0
        span = item["span"]
        start, end = span.get("start"), span.get("end")
        assert 0 <= start < end <= len(item["text"])
        snippet_lower = item["snippet"].lower()
        text_lower = item["text"].lower()
        if any(s in text_lower for s in stems):
            assert any(s in snippet_lower for s in stems)
