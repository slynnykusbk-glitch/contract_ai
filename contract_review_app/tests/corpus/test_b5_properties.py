import os
from typing import List

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from contract_review_app.corpus.db import get_engine, init_db, SessionLocal
from contract_review_app.corpus.repo import Repo, CorpusRecord


@pytest.fixture
def repo(tmp_path):
    dsn = f"sqlite:///{tmp_path / 'corpus_prop.db'}"
    os.environ["LEGAL_CORPUS_DSN"] = dsn
    engine = get_engine(dsn)
    init_db(engine)
    session = SessionLocal(bind=engine)
    return Repo(session)


def build_dto(version: str, text: str) -> CorpusRecord:
    return {
        "source": "legislation.gov.uk",
        "jurisdiction": "UK",
        "act_code": "UK_GDPR",
        "act_title": "UK GDPR",
        "section_code": "Art.5",
        "section_title": "Principles of processing",
        "version": version,
        "updated_at": "2024-06-01T00:00:00Z",
        "rights": "Crown",
        "lang": "en",
        "script": "Latn",
        "text": text,
    }


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    st.integers(min_value=1, max_value=5).flatmap(
        lambda n: st.permutations([f"2024-{i:02d}" for i in range(1, n + 1)])
    )
)
def test_latest_singleton_property(repo, versions: List[str]):
    repo.delete_all()
    for v in versions:
        repo.upsert(build_dto(v, f"Text {v}"))
        assert repo.group_latest_count("UK", "UK_GDPR", "Art.5") == 1

    latest = repo.list_latest({"jurisdiction": "UK", "act_code": "UK_GDPR"})
    assert len(latest) == 1
    assert latest[0].version == max(versions)


@st.composite
def variant_text(draw):
    base = "  Text with \"quotes\"  and  spaces  "
    text = base
    if draw(st.booleans()):
        text = text.replace(" ", "\u00A0")
    if draw(st.booleans()):
        text = text.replace("\"", "“")
    if draw(st.booleans()):
        text = text.replace("\"", "”")
    if draw(st.booleans()):
        text = "  " + text + "   "
    if draw(st.booleans()):
        text = text.replace("  ", "     ")
    return text


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(st.lists(variant_text(), min_size=1, max_size=5))
def test_checksum_normalization_property(repo, texts):
    repo.delete_all()
    version = "2024-01"
    first_id = None
    for t in texts:
        doc = repo.upsert(build_dto(version, t))
        if first_id is None:
            first_id = doc.id
        else:
            assert doc.id == first_id
        assert repo.group_latest_count("UK", "UK_GDPR", "Art.5") == 1

    all_docs = repo.find(jurisdiction="UK", act_code="UK_GDPR", section_code="Art.5")
    assert len(all_docs) == 1
    assert all_docs[0].version == version


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(st.lists(st.sampled_from(["2024-01", "2024-02", "2024-03"]), min_size=1, max_size=3, unique=True))
def test_unique_version_invariant(repo, versions):
    repo.delete_all()
    for v in versions:
        repo.upsert(build_dto(v, f"original {v}"))
        repo.upsert(build_dto(v, f"updated {v}"))

    docs = repo.find(jurisdiction="UK", act_code="UK_GDPR", section_code="Art.5")
    assert len(docs) == len(versions)
    assert {d.version for d in docs} == set(versions)

    assert repo.group_latest_count("UK", "UK_GDPR", "Art.5") == 1
