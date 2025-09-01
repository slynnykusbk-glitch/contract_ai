from dataclasses import dataclass
from typing import List, Dict, Any
import os

@dataclass
class DraftResult:
    proposed_text: str
    rationale: str
    evidence: List[Dict[str, Any]]
    before_text: str
    after_text: str
    diff_unified: str
    # optional metadata for headers
    provider: str = ""
    model: str = ""
    mode: str = ""
    usage: Dict[str, Any] | None = None

class LLMProvider:
    def draft(self, text: str, mode: str = "friendly") -> DraftResult:  # pragma: no cover - interface
        raise NotImplementedError

def provider_from_env() -> "LLMProvider":
    prov = (os.getenv("CONTRACTAI_PROVIDER", "mock") or "").lower()
    if prov == "azure":
        from .azure import AzureProvider
        return AzureProvider()
    from .mock import MockProvider
    return MockProvider()
