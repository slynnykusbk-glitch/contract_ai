from fastapi.testclient import TestClient
from contract_review_app.api.app import app


client = TestClient(app)

TEXT = (
    "This Agreement is governed by the laws of England and Wales. "
    "Each party shall keep the other's information confidential. "
    "Company may audit the records at any time."
)


def test_findings_schema_fields():
    r = client.post("/api/analyze", json={"text": TEXT})
    assert r.status_code == 200
    findings = r.json()["analysis"]["findings"]
    assert len(findings) >= 3
    for f in findings:
        for key in [
            "rule_id",
            "clause_type",
            "severity",
            "start",
            "end",
            "snippet",
            "advice",
            "law_refs",
            "conflict_with",
            "ops",
            "scope",
            "occurrences",
        ]:
            assert key in f
        assert isinstance(f["law_refs"], list)
        assert isinstance(f["conflict_with"], list)
        assert isinstance(f["ops"], list)
        assert isinstance(f["occurrences"], int) and f["occurrences"] >= 1
        assert isinstance(f["scope"], dict)
