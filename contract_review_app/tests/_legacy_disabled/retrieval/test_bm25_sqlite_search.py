import yaml
from pathlib import Path

import yaml
from pathlib import Path

import pytest

from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from contract_review_app.corpus.repo import Repo
from contract_review_app.retrieval.indexer import rebuild_index
from contract_review_app.retrieval.search import BM25Search
from contract_review_app.corpus.models import CorpusDoc


@pytest.fixture
def session(tmp_path):
    dsn = f"sqlite:///{tmp_path/'corpus.db'}"
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


def test_search_gdpr_article5(session):
    searcher = BM25Search(session)
    res = searcher.search("transparent processing", jurisdiction="UK")
    assert any(r["act_code"] == "UK_GDPR" and r["section_code"] == "Art.5" for r in res)


def test_filters_work(session):
    searcher = BM25Search(session)
    res = searcher.search("pollution")
    assert any(r["act_code"] == "OGUK_MODEL" for r in res)
    res2 = searcher.search("pollution", source="legislation.gov.uk")
    assert all(r["act_code"] != "OGUK_MODEL" for r in res2)


def test_deterministic_ordering(session):
    searcher = BM25Search(session)
    r1 = searcher.search("data")
    r2 = searcher.search("data")
    assert [x["id"] for x in r1] == [x["id"] for x in r2]


def test_span_bounds(session):
    searcher = BM25Search(session)
    res = searcher.search("data", jurisdiction="UK")
    for r in res:
        doc = session.get(CorpusDoc, r["corpus_id"])
        assert 0 <= r["start"] < r["end"] <= len(doc.text)
