from types import SimpleNamespace

from contract_review_app.llm.orchestrator import Orchestrator
from contract_review_app.llm.provider import LLMConfig


class EchoProvider:
    def __init__(self, include_markers: bool = True):
        self.include_markers = include_markers

    def generate(self, prompt: str, config: LLMConfig):
        text = prompt
        if not self.include_markers:
            import re

            text = re.sub(r"\[c\d+\]", "", text)
        return SimpleNamespace(text=text, usage={}, model="mock", provider="mock")


def _sample_citations():
    return [
        {
            "system": "UK",
            "instrument": "Act1",
            "section": "10",
            "url": "https://www.legislation.gov.uk/a",
        },
        {
            "system": "UK",
            "instrument": "Act2",
            "section": "20",
            "url": "https://example.com/bad",
        },
        "Act3",
    ]


def test_draft_with_citations_verified():
    orch = Orchestrator(EchoProvider(True))
    out = orch.draft(question="Q", context_text="Ctx", citations=_sample_citations())
    assert "> [c1]" in out["prompt"]
    assert [e["id"] for e in out["grounding_trace"]["evidence"]] == ["c1", "c2", "c3"]
    assert out["verification_status"] == "verified"


def test_suggest_edits_unverified_when_markers_absent():
    orch = Orchestrator(EchoProvider(False))
    out = orch.suggest_edits(
        question="Q", context_text="Ctx", citations=_sample_citations()
    )
    assert out["verification_status"] == "unverified"
    assert "> [c1]" in out["prompt"]
