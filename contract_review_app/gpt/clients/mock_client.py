from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class MockClient(BaseClient):
    def __init__(self, model: str):
        self.provider = "mock"
        self.model = model
        self.mode = "mock"

    def _check_timeout(self, timeout: float):
        if timeout and timeout < 0.05:
            raise ProviderTimeoutError(self.provider, timeout)

    def draft(self, prompt: str, max_tokens: int, temperature: float, timeout: float) -> DraftResult:
        self._check_timeout(timeout)
        snippet = prompt[: max_tokens].strip() if prompt else ""
        if not snippet:
            snippet = "example"
        text = f"[MOCK DRAFT] {snippet}"
        return DraftResult(text=text, meta={"provider": self.provider, "model": self.model, "mode": self.mode})

    def suggest_edits(self, prompt: str, timeout: float) -> SuggestResult:
        self._check_timeout(timeout)
        items = [{"text": "No change needed", "risk": "low"}]
        return SuggestResult(items=items, meta={"provider": self.provider, "model": self.model, "mode": self.mode})

    def qa_recheck(self, prompt: str, timeout: float) -> QAResult:
        self._check_timeout(timeout)
        items = [{"id": "1", "status": "ok", "note": "All checks passed"}]
        return QAResult(items=items, meta={"provider": self.provider, "model": self.model, "mode": self.mode})
