import yaml
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from contract_review_app.corpus.repo import Repo
from contract_review_app.retrieval.indexer import rebuild_index
from contract_review_app.api.corpus_search import router
from contract_review_app.api.limits import MAX_PAGE_SIZE


def _setup_demo(session):
    repo = Repo(session)
    for p in Path('data/corpus_demo').glob('*.yaml'):
        with open(p, 'r', encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
            for item in data['items']:
                repo.upsert(item)


def _make_client(tmp_path):
    dsn = f"sqlite:///{tmp_path/'api.db'}"
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:
        _setup_demo(session)
        rebuild_index(session)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_pagination_basic(tmp_path):
    client = _make_client(tmp_path)
    r = client.post("/api/corpus/search?page=1&page_size=2", json={"q": "processing"})
    assert r.status_code == 200
    data = r.json()
    assert len(data['hits']) == 2
    assert data['paging']['total'] == 5
    assert data['paging']['pages'] == 3

    r = client.post("/api/corpus/search?page=3&page_size=2", json={"q": "processing"})
    assert r.status_code == 200
    data = r.json()
    assert len(data['hits']) == 1


def test_page_size_validation(tmp_path):
    client = _make_client(tmp_path)
    r = client.post(f"/api/corpus/search?page_size={MAX_PAGE_SIZE + 1}", json={"q": "processing"})
    assert r.status_code == 422
