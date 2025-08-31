from pathlib import Path

import pytest
import yaml
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
def session(tmp_path, monkeypatch):
    dsn = f"sqlite:///{tmp_path/'api.db'}"
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    sess = SessionLocal()
    repo = Repo(sess)
    demo_dir = Path('data/corpus_demo')
    for p in demo_dir.glob('*.yaml'):
        with open(p, 'r', encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
            for item in data['items']:
                repo.upsert(item)
    rebuild_index(sess)
    cache_dir = tmp_path / 'cache'
    monkeypatch.setenv('RETRIEVAL_CACHE_DIR', str(cache_dir))
    cfg = load_config()
    embedder = HashingEmbedder(cfg['vector']['embedding_dim'])
    ensure_vector_cache(
        sess,
        embedder=embedder,
        cache_dir=cfg['vector']['cache_dir'],
        emb_ver=cfg['vector']['embedding_version'],
    )
    yield sess
    sess.close()


def test_vector_and_hybrid_modes(session, monkeypatch):
    from contract_review_app.retrieval import search as rsearch

    calls = []
    orig = rsearch.ensure_vector_cache

    def wrapper(*args, **kwargs):
        vecs, ids, metas, from_cache = orig(*args, **kwargs)
        calls.append(from_cache)
        return vecs, ids, metas, from_cache

    monkeypatch.setattr(rsearch, 'ensure_vector_cache', wrapper)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.get('/api/corpus/search', params={'q': 'data', 'mode': 'vector'})
    assert r.status_code == 200
    assert r.json()['results']
    r2 = client.get('/api/corpus/search', params={'q': 'data', 'mode': 'hybrid'})
    assert r2.status_code == 200
    assert r2.json()['results']
    assert calls == [True, True]
