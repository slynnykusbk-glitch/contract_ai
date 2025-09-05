from fastapi.testclient import TestClient
from contract_review_app.api.app import app


client = TestClient(app)


def test_anchor_sentence_scope():
    text = "Confidential information must be protected. Another sentence."
    r = client.post("/api/analyze", json={"text": text})
    assert r.status_code == 200
    f = r.json()["analysis"]["findings"][0]
    sentence = "Confidential information must be protected."
    assert f["snippet"] == sentence
    assert f["start"] == 0
    assert f["end"] == len(sentence)
