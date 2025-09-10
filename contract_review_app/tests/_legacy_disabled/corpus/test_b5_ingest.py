import os
from pathlib import Path

import yaml

from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from contract_review_app.corpus.repo import Repo
from contract_review_app.corpus.ingest import run_ingest, to_repo_dto


def setup_sqlite(tmp_path):
    dsn = f"sqlite:///{tmp_path / 'corpus.db'}"
    os.environ["LEGAL_CORPUS_DSN"] = dsn
    engine = get_engine(dsn)
    init_db(engine)
    return dsn


ITEM_ART5 = {
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
    "text": "Personal data shall be processed lawfully, fairly and in a transparent manner…",
}

ITEM_ART28 = {
    "source": "legislation.gov.uk",
    "jurisdiction": "UK",
    "act_code": "UK_GDPR",
    "act_title": "UK GDPR",
    "section_code": "Art.28",
    "section_title": "Processor",
    "version": "2024-06",
    "updated_at": "2024-06-01T00:00:00Z",
    "url": "https://www.legislation.gov.uk/eur/2016/679/article/28",
    "rights": "Open Government Licence v3.0",
    "lang": "en",
    "script": "Latn",
    "text": "The processor shall not engage another processor without prior authorisation of the controller.",
}

ITEM_UCTA = {
    "source": "legislation.gov.uk",
    "jurisdiction": "UK",
    "act_code": "UCTA_1977",
    "act_title": "Unfair Contract Terms Act 1977",
    "section_code": "s.2",
    "section_title": "Negligence liability",
    "version": "2020-01",
    "updated_at": "2020-01-01T00:00:00Z",
    "url": "https://www.legislation.gov.uk/ukpga/1977/50/section/2",
    "rights": "Open Government Licence v3.0",
    "lang": "en",
    "script": "Latn",
    "text": "A person cannot exclude or restrict liability for negligence resulting in death or personal injury.",
}


def _write_items(dir_path: Path, items):
    with open(dir_path / "demo.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump({"items": items}, fh, sort_keys=False, allow_unicode=True)


def test_ingest_demo_dir_idempotent(tmp_path):
    dsn = setup_sqlite(tmp_path)
    demo_dir = tmp_path / "dir"
    demo_dir.mkdir()
    _write_items(demo_dir, [ITEM_ART5, ITEM_ART28, ITEM_UCTA])

    n1 = run_ingest(str(demo_dir), dsn=dsn)
    assert n1 == 3
    n2 = run_ingest(str(demo_dir), dsn=dsn)
    assert n2 == 3

    session = SessionLocal(bind=get_engine(dsn))
    repo = Repo(session)
    latest_docs = repo.list_latest()
    assert len(latest_docs) == 3
    assert all(doc.latest for doc in latest_docs)
    keys = {(d.jurisdiction, d.act_code, d.section_code) for d in latest_docs}
    assert len(keys) == 3
    all_docs = repo.find()
    assert len(all_docs) == 3


def test_find_query_and_titles(tmp_path):
    dsn = setup_sqlite(tmp_path)
    demo_dir = tmp_path / "dir"
    demo_dir.mkdir()
    _write_items(demo_dir, [ITEM_ART5])
    run_ingest(str(demo_dir), dsn=dsn)

    session = SessionLocal(bind=get_engine(dsn))
    repo = Repo(session)
    res = repo.find(jurisdiction="UK", act_code="UK_GDPR", q="transparent")
    assert len(res) == 1
    res2 = repo.find(jurisdiction="UK", act_code="UK_GDPR", q="Principles")
    assert len(res2) == 1


def test_checksum_normalization(tmp_path):
    dsn = setup_sqlite(tmp_path)
    engine = get_engine(dsn)
    session = SessionLocal(bind=engine)
    repo = Repo(session)

    item = {
        "source": "legislation.gov.uk",
        "jurisdiction": "UK",
        "act_code": "UK_GDPR",
        "act_title": "UK GDPR",
        "section_code": "Art.5",
        "section_title": "Principles",
        "version": "2024-06",
        "updated_at": "2024-06-01T00:00:00Z",
        "rights": "Open Government Licence v3.0",
        "text": "Data must be processed lawfully\u00A0and “fairly”.",
    }
    dto1 = to_repo_dto(item)
    repo.upsert(dto1)

    item2 = dict(item)
    item2["text"] = "Data must be processed lawfully and \"fairly\"."
    dto2 = to_repo_dto(item2)
    assert dto1["checksum"] == dto2["checksum"]
    repo.upsert(dto2)

    all_docs = repo.find()
    assert len(all_docs) == 1
