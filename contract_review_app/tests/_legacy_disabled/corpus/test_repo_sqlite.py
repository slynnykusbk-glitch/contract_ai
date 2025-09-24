import os
from datetime import timedelta, timezone

import pytest

from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from contract_review_app.corpus.repo import CorpusRepository, CorpusRecord


@pytest.fixture
def repo(tmp_path):
    dsn = f"sqlite:///{tmp_path / 'corpus.db'}"
    os.environ["LEGAL_CORPUS_DSN"] = dsn
    engine = get_engine(dsn)
    init_db(engine)
    session = SessionLocal(bind=engine)
    return CorpusRepository(session)


def build_dto(version: str, text: str) -> CorpusRecord:
    return {
        "source": "gov.uk",
        "jurisdiction": "UK",
        "act_code": "UK_GDPR",
        "act_title": "UK GDPR",
        "section_code": "Art5",
        "section_title": "Principles of processing",
        "version": version,
        "updated_at": "2024-06-01T00:00:00Z",
        "rights": "CC-BY",
        "lang": "en",
        "script": "Latn",
        "text": text,
    }


def test_happy_path_and_latest(repo):
    dto1 = build_dto("2024-06", "Text with\u00a0NBSP and “quotes”.")
    doc1 = repo.upsert(dto1)

    latest = repo.list_latest()
    assert len(latest) == 1
    assert latest[0].latest is True

    dto2 = build_dto("2025-01", "Updated text with different content.")
    repo.upsert(dto2)

    all_docs = repo.find()
    assert len(all_docs) == 2
    old = repo.get_by_key("UK", "UK_GDPR", "Art5", "2024-06")
    new = repo.get_by_key("UK", "UK_GDPR", "Art5", "2025-01")
    assert old.latest is False
    assert new.latest is True


def test_idempotent_same_checksum(repo):
    dto = build_dto("2024-06", "Some text")
    repo.upsert(dto)
    repo.upsert(dto)
    all_docs = repo.find()
    assert len(all_docs) == 1


def test_find_and_titles(repo):
    dto = build_dto(
        "2024-06",
        "Information shall be processed in a transparent manner.",
    )
    repo.upsert(dto)

    res = repo.find(jurisdiction="UK", act_code="UK_GDPR", q="transparent")
    assert len(res) == 1

    res2 = repo.find(jurisdiction="UK", act_code="UK_GDPR", q="Principles")
    assert len(res2) == 1


def test_updated_at_utc(repo):
    dto = build_dto("2024-06", "Some text")
    doc = repo.upsert(dto)
    assert doc.updated_at.tzinfo is not None
    assert doc.updated_at.utcoffset() == timedelta(0)
