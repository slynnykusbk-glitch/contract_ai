import json
from pathlib import Path

import pytest

from contract_review_app.corpus.db import SessionLocal, get_engine, init_db
from contract_review_app.corpus.ingest import run_ingest
from contract_review_app.retrieval.indexer import rebuild_index
from contract_review_app.retrieval.eval import evaluate, load_golden

GOLDEN_PATH = Path("data/retrieval_golden.yaml")


@pytest.fixture(scope="session", autouse=True)
def prepare_demo():
    import os

    dsn = f"sqlite:///{(Path('.local') / 'corpus.db').resolve()}"
    os.environ["LEGAL_CORPUS_DSN"] = dsn
    run_ingest("data/corpus_demo", dsn=dsn)
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:
        rebuild_index(session)


@pytest.fixture(autouse=True)
def fusion_env(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_FUSION_METHOD", "weighted")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_VECTOR", "0.4")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_BM25", "0.6")


@pytest.fixture(scope="module")
def golden() -> list:
    return load_golden(str(GOLDEN_PATH))


def test_hybrid_metrics(golden):
    res1 = evaluate(golden, "hybrid", 5)
    res2 = evaluate(golden, "hybrid", 5)
    assert res1["recall_at_k"] >= 0.8
    assert res1["mrr_at_k"] > 0.6
    assert res1 == res2


def test_bm25_smoke(golden):
    res = evaluate(golden, "bm25", 5)
    assert res["recall_at_k"] >= 0.6


def test_vector_smoke(golden):
    res = evaluate(golden, "vector", 5)
    assert res["recall_at_k"] >= 0.6
