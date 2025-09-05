from fastapi.testclient import TestClient
from contract_review_app.api.app import app


client = TestClient(app)


def test_aggregation_dedup():
    word = "confidential"
    repeated = " ".join([word] * 20)
    text = f"1. {repeated}"
    r = client.post("/api/analyze", json={"text": text})
    assert r.status_code == 200
    f = r.json()["analysis"]["findings"][0]
    assert f["occurrences"] == 20
    assert f["start"] == 0
    assert f["end"] == len(text)
