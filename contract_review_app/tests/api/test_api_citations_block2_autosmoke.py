import os
import re
import asyncio
import httpx
import pytest

from contract_review_app.api.app import app


# Helper: split text into language segments with spans
_WORD_RE = re.compile(r"[A-Za-z]+|[А-Яа-яЁёЇїІіЄєҐґ]+")

def _split_words(text: str):
    for m in _WORD_RE.finditer(text):
        word = m.group(0)
        lang = "latin" if word.isascii() else "cyrillic"
        yield (m.start(), m.end()), word, lang


def _fake_analyze(text: str):
    findings = []
    for (s, e), word, lang in _split_words(text):
        findings.append({"span": {"start": s, "end": e}, "text": word, "lang": lang})
    results = {"analysis": {"findings": findings}}
    if os.getenv("CONTRACTAI_INTAKE_NORMALIZE") == "1":
        results["analysis"]["segments"] = [
            {"span": f["span"], "text": f["text"], "lang": f["lang"]}
            for f in findings
        ]
    return {"status": "OK", "results": results}


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    yield client
    asyncio.run(client.aclose())


def test_api_citations_block2_no_flag(monkeypatch, client):
    monkeypatch.setattr("contract_review_app.api.app._analyze_document", _fake_analyze, raising=True)
    resp = asyncio.run(client.post("/api/analyze", json={"text": "Hello World"}))
    assert resp.status_code == 200
    data = resp.json()
    findings = data["results"]["analysis"]["findings"]
    assert findings == [
        {"span": {"start": 0, "end": 5}, "text": "Hello", "lang": "latin"},
        {"span": {"start": 6, "end": 11}, "text": "World", "lang": "latin"},
    ]


def test_api_citations_block2_with_feature_flag(monkeypatch, client):
    monkeypatch.setattr("contract_review_app.api.app._analyze_document", _fake_analyze, raising=True)
    monkeypatch.setenv("CONTRACTAI_INTAKE_NORMALIZE", "1")
    raw_text = "“Hello\u00A0World”—Привіт"
    resp = asyncio.run(client.post("/api/analyze", json={"text": raw_text}))
    assert resp.status_code == 200
    data = resp.json()
    findings = data["results"]["analysis"]["findings"]
    raw_len = len(raw_text)
    for f in findings:
        start, end = f["span"]["start"], f["span"]["end"]
        assert 0 <= start < end <= raw_len
        assert raw_text[start:end] == f["text"]
    segments = data["results"]["analysis"].get("segments", [])
    langs = {seg.get("lang") for seg in segments}
    assert "latin" in langs and "cyrillic" in langs


def test_api_citations_block2_idempotence(monkeypatch, client):
    monkeypatch.setattr("contract_review_app.api.app._analyze_document", _fake_analyze, raising=True)
    monkeypatch.setenv("CONTRACTAI_INTAKE_NORMALIZE", "1")
    payload = {"text": "“Hello\u00A0World”—Привіт"}
    resp1 = asyncio.run(client.post("/api/analyze", json=payload))
    resp2 = asyncio.run(client.post("/api/analyze", json=payload))
    assert resp1.status_code == 200 and resp2.status_code == 200
    assert resp1.json() == resp2.json()
