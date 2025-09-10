import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from contract_review_app.core.corpus_schemas import (
    CorpusDocMeta,
    CorpusDocument,
    OGL_V3,
)


def _meta(**kwargs):
    data = {
        "source": "legislation",
        "jurisdiction": "UK",
        "act": "Some Act",
        "section": "10",
        "version": "1",
        "updated_at": "2023-01-01T00:00:00",
        "url": "https://example.com",
        "rights": OGL_V3,
    }
    data.update(kwargs)
    return CorpusDocMeta(**data)


def test_happy_path():
    meta = _meta(lang="en")
    doc = CorpusDocument(meta=meta, content="  lorem ipsum  ")
    assert doc.meta == meta
    assert doc.content == "lorem ipsum"


def test_empty_fields_raise():
    with pytest.raises(ValidationError):
        _meta(source=" ")
    with pytest.raises(ValidationError):
        CorpusDocument(meta=_meta(), content="  ")


def test_updated_at_utc():
    meta = _meta(updated_at=datetime(2023, 1, 1, 12, 0, 0))
    assert meta.updated_at.tzinfo == timezone.utc


def test_round_trip():
    meta = _meta(lang=None)
    dumped = meta.model_dump(exclude_none=True)
    meta2 = CorpusDocMeta.model_validate(dumped)
    assert meta2 == meta
    doc = CorpusDocument(meta=meta, content="text")
    doc_dump = doc.model_dump(exclude_none=True)
    doc2 = CorpusDocument.model_validate(doc_dump)
    assert doc2 == doc


def test_hashability():
    m1 = _meta()
    m2 = _meta()
    assert m1 == m2
    s = {m1, m2}
    assert len(s) == 1
    d1 = CorpusDocument(meta=m1, content="abc")
    d2 = CorpusDocument(meta=m2, content="abc")
    assert d1 == d2
    assert len({d1, d2}) == 1
