from contract_review_app.llm.citation_resolver import make_grounding_pack
from contract_review_app.llm.prompt_builder import build_prompt


def test_grounding_includes_evidence_block():
    citations = [{"system": "UK", "instrument": "Act", "section": "1"}]
    gp = make_grounding_pack("", "Context text", citations)
    prompt = build_prompt(mode="friendly", grounding=gp)
    assert "EVIDENCE:" in prompt
    assert "[c1]" in prompt
