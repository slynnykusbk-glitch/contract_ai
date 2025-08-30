import os
from pathlib import Path

import yaml

from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from contract_review_app.corpus.repo import Repo
from contract_review_app.corpus.ingest import run_ingest, to_repo_dto



def setup_sqlite(tmp_path):
    dsn = f"sqlite:///{tmp_path/'corpus.db'}"
    os.environ["LEGAL_CORPUS_DSN"] = dsn
    engine = get_engine(dsn)
    init_db(engine)
    return dsn


def _demo_items():
    return [
        {
            "source": "legislation.gov.uk",
            "jurisdiction": "UK",
            "act_code": "UK_GDPR",
            "act_title": "UK GDPR",
            "section_code": "Art.5",
            "section_title": "Principles relating to processing of personal data",
            "version": "2024-06",
            "updated_at": "2024-06-01T00:00:00Z",
            "url": "https://www.legislation.gov.uk/eur/2016/679/article/5",
            "rights": "Open Government Licence v3.0",
            "lang": "en",
            "script": "Latn",
            "text": "Personal data shall be processed lawfully, fairly and in a transparent manner",
        },
        {
            "source": "legislation.gov.uk",
            "jurisdiction": "UK",
            "act_code": "UCTA_1977",
            "act_title": "Unfair Contract Terms Act 1977",
            "section_code": "s.2",
            "section_title": "Negligence liability",
            "version": "2024-06",
            "updated_at": "2024-06-01T00:00:00Z",
            "url": "https://www.legislation.gov.uk/ukpga/1977/50/section/2",
            "rights": "Open Government Licence v3.0",
            "lang": "en",
            "script": "Latn",
            "text": "A person cannot by reference to any contract term restrict his liability",
        },
        {
            "source": "OGUK",
            "jurisdiction": "UK",
            "act_code": "OGUK_MODEL",
            "act_title": "OGUK Model Form",
            "section_code": "Indemnity",
            "section_title": "Sample mutual indemnity clause",
            "version": "2024-06",
            "updated_at": "2024-06-01T00:00:00Z",
            "rights": "OGUK Licence",
            "lang": "en",
            "script": "Latn",
            "text": "Each party shall indemnify the other against all claims and losses",
        },
    ]


def test_ingest_demo_dir_idempotent(tmp_path):
    dsn = setup_sqlite(tmp_path)
    demo_dir = tmp_path / "dir"
    demo_dir.mkdir()
    data = {"items": _demo_items()}
    with open(demo_dir / "demo.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True)

    n1 = run_ingest(str(demo_dir), dsn=dsn)
    assert n1 == len(data["items"])
    n2 = run_ingest(str(demo_dir), dsn=dsn)
    assert n2 == len(data["items"])

    session = SessionLocal()
    repo = Repo(session)
    docs = repo.list_latest()
    assert len(docs) == len(data["items"])
    combos = {(d.jurisdiction, d.act_code, d.section_code) for d in docs}
    assert len(combos) == len(data["items"])
    for d in docs:
        assert d.latest is True
    session.close()


def test_find_query_and_titles(tmp_path):
    dsn = setup_sqlite(tmp_path)
    demo_dir = tmp_path / "dir"
    demo_dir.mkdir()
    items = _demo_items()
    with open(demo_dir / "demo.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump({"items": items}, fh, allow_unicode=True)
    run_ingest(str(demo_dir), dsn=dsn)
    session = SessionLocal()
    repo = Repo(session)
    res1 = repo.find(jurisdiction="UK", act_code="UK_GDPR", q="transparent")
    assert res1
    res2 = repo.find(jurisdiction="UK", act_code="UK_GDPR", q="Principles")
    assert res2
    session.close()


def test_checksum_normalization(tmp_path):
    dsn = setup_sqlite(tmp_path)
    session = SessionLocal()
    repo = Repo(session)
    item = {
        "source": "legislation.gov.uk",
        "jurisdiction": "UK",
        "act_code": "UK_GDPR",
        "act_title": "UK GDPR",
        "section_code": "Art.99",
        "section_title": "Special provision",
        "version": "2024-06",
        "updated_at": "2024-06-01T00:00:00Z",
        "rights": "Open Government Licence v3.0",
        "lang": "en",
        "script": "Latn",
        "text": "Quotes\u00A0and “spaces”",
    }
    dto1 = to_repo_dto(item)
    repo.upsert(dto1)
    item["text"] = 'Quotes and "spaces"'
    dto2 = to_repo_dto(item)
    repo.upsert(dto2)
    docs = repo.list_latest()
    assert len(docs) == 1
    session.close()
