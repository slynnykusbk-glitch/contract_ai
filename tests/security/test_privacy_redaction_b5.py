from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_privacy_redaction_and_scrub():
    text = (
        "Contact John Smith at john@example.com or +44 1234 567890. "
        "NI AB123456C."
    )
    r = client.post("/api/gpt-draft", json={"text": text, "mode": "friendly"})
    assert r.status_code == 200
    data = r.json()
    sensitive = ["John Smith", "john@example.com", "+44 1234 567890", "AB123456C"]
    combined = " ".join(
        [
            data.get("proposed_text", ""),
            data.get("rationale", ""),
            data.get("after_text", ""),
            data.get("diff", {}).get("value", ""),
            " ".join(data.get("evidence", [])),
        ]
    )
    for item in sensitive:
        assert item not in combined
