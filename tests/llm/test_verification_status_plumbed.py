from fastapi import FastAPI
from fastapi.testclient import TestClient

from contract_review_app.llm.api_dto import LLMResponse
from contract_review_app.llm.citation_resolver import make_grounding_pack
from contract_review_app.llm.verification import verify_output_contains_citations
from contract_review_app.gpt.gpt_draft_api import router as draft_router


def test_verification_status_propagates_and_triggers_fallback():
    gp = make_grounding_pack("", "Some clause", [{"instrument": "Act", "section": "1"}])
    status = verify_output_contains_citations("no refs", gp["evidence"])
    resp = LLMResponse(provider="test", model="m", result="r", prompt="p", verification_status=status)
    assert resp.verification_status == "unverified"

    app = FastAPI()
    app.include_router(draft_router)
    client = TestClient(app)
    payload = {
        "analysis": {
            "clause_type": "Test",
            "text": "Clause text",
            "citations": [{"instrument": "Act", "section": "1"}],
        }
    }
    r = client.post("/api/gpt-draft", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["verification_status"] == "unverified"
    assert not data["draft_text"].startswith("UPDATED:")
