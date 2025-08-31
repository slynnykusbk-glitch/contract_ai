import yaml
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from contract_review_app.corpus.repo import Repo
from contract_review_app.retrieval.indexer import rebuild_index
from contract_review_app.api.corpus_search import router


def _setup_demo(session):
    repo = Repo(session)
    for p in Path('data/corpus_demo').glob('*.yaml'):
        with open(p, 'r', encoding='utf-8') as fh:
            data = yaml.safe_load(fh)
            for item in data['items']:
                repo.upsert(item)


def test_corpus_search_api(tmp_path):
    dsn = f"sqlite:///{tmp_path/'api.db'}"
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:
        _setup_demo(session)
        rebuild_index(session)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.get("/api/corpus/search", params={"q": "processing", "jurisdiction": "UK", "top": 3})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("results"), list)
    assert data["results"]
    item = data["results"][0]
    assert {"id", "meta", "span", "text", "score"}.issubset(item.keys())
