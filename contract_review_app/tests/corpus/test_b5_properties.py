"""Property tests for legal corpus invariants."""

# ruff: noqa: E402

import os
import re

import pytest
from sqlalchemy import select, func

from contract_review_app.corpus import (
    CorpusDTO,
    Repo,
    SessionLocal,
    get_engine,
    init_db,
    LegalCorpus,
)

hypothesis = pytest.importorskip(
    "hypothesis", reason="property tests require hypothesis"
)
from hypothesis import (
    HealthCheck,
    given,
    settings,
    strategies as st,
)  # noqa: E402


@pytest.fixture()
def repo(tmp_path):
    dsn = f"sqlite:///{tmp_path/'corpus_prop.db'}"
    os.environ["LEGAL_CORPUS_DSN"] = dsn
    engine = get_engine(dsn)
    init_db(engine)
    SessionLocal.configure(bind=engine)
    return Repo(SessionLocal)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    st.permutations(["2024-01", "2024-02", "2024-03", "2024-04"]),
    st.lists(st.text(min_size=1), min_size=4, max_size=4),
)
def test_latest_singleton_property(repo, versions, noises):
    j, a, s = "UK", "UK_GDPR", "Art.5"
    for v, noise in zip(versions, noises):
        text = f"Article text {v} {noise}"
        repo.upsert(
            CorpusDTO(jurisdiction=j, act_code=a, section_code=s, version=v, text=text)
        )
        assert repo.group_latest_count(j, a, s) == 1

    latest = repo.list_latest({"jurisdiction": j, "act_code": a})
    assert latest and latest[0].version == max(versions)


_base_text = " \"Hello\" world and \n\n\t'quotes' "


def _variant(base, nbsp, curly, multispace):
    text = base
    if nbsp:
        text = text.replace(" ", "\u00a0")
    if curly:
        text = text.replace('"', "\u201c").replace("'", "\u2019")
    if multispace:
        text = re.sub(" ", "  ", text)
    return text


variant_strategy = st.builds(
    _variant,
    st.just(_base_text),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.lists(variant_strategy, min_size=1, max_size=5))
def test_checksum_normalization_property(repo, variants):
    j, a, s, v = "UK", "UK_GDPR", "Art.5", "2024-01"
    checksums = set()
    for text in variants:
        row = repo.upsert(CorpusDTO(j, a, s, v, text))
        checksums.add(row.checksum)
    assert len(checksums) == 1

    with repo.Session() as session:
        count = session.scalar(
            select(func.count()).where(
                LegalCorpus.jurisdiction == j,
                LegalCorpus.act_code == a,
                LegalCorpus.section_code == s,
                LegalCorpus.version == v,
            )
        )
    assert count == 1


def test_unique_version_invariant(repo):
    j, a, s, v = "UK", "UK_GDPR", "Art.5", "2024-02"
    repo.upsert(CorpusDTO(j, a, s, v, "first"))
    repo.upsert(CorpusDTO(j, a, s, v, "second"))

    with repo.Session() as session:
        rows = (
            session.execute(
                select(LegalCorpus).where(
                    LegalCorpus.jurisdiction == j,
                    LegalCorpus.act_code == a,
                    LegalCorpus.section_code == s,
                    LegalCorpus.version == v,
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].text == "second"
