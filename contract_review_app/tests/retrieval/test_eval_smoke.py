import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from contract_review_app.corpus.db import SessionLocal, get_engine, init_db
from contract_review_app.corpus.ingest import run_ingest
from contract_review_app.retrieval.indexer import rebuild_index

GOLDEN_PATH = Path("data/retrieval_golden.yaml")


@pytest.fixture(scope="session", autouse=True)
def prepare_demo(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("retrieval-demo")
    dsn = f"sqlite:///{(tmp_dir / 'corpus.db').resolve()}"
    os.environ["LEGAL_CORPUS_DSN"] = dsn
    run_ingest("data/corpus_demo", dsn=dsn)
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    with SessionLocal() as session:
        rebuild_index(session)
    cache_dir = tmp_dir / "cache"
    os.environ["RETRIEVAL_CACHE_DIR"] = str(cache_dir)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "contract_review_app.retrieval.cli",
            "build",
        ],
        check=True,
    )


@pytest.fixture(autouse=True)
def fusion_env(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_FUSION_METHOD", "weighted")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_VECTOR", "0.4")
    monkeypatch.setenv("RETRIEVAL_WEIGHT_BM25", "0.6")


def test_eval_cli():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "contract_review_app.retrieval.eval",
            "--golden",
            str(GOLDEN_PATH),
            "--method",
            "hybrid",
            "--k",
            "5",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout.strip() or "{}")
    assert "recall_at_k" in data and "mrr_at_k" in data
