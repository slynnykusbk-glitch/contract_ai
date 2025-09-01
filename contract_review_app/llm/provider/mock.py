import difflib
from .base import LLMProvider, DraftResult

class MockProvider(LLMProvider):
    def draft(self, text: str, mode: str = "friendly") -> DraftResult:
        before = text or ""
        after = before.strip() + "\n\n[Mock suggestion: tighten confidentiality carve-outs.]"
        diff = "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))
        return DraftResult(
            proposed_text=after,
            rationale=f"Mock rationale (mode={mode}).",
            evidence=[],
            before_text=before,
            after_text=after,
            diff_unified=diff,
            provider="mock",
            model="mock-draft",
            mode=mode,
            usage={"total_tokens": 0},
        )
