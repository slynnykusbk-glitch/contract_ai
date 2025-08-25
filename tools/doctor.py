"""Simple smoke diagnostics for LLM client/service wiring."""
import pathlib
import os
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from contract_review_app.gpt.interfaces import (
    BaseClient,
    DraftResult,
    SuggestResult,
    QAResult,
    ProviderTimeoutError,
    ProviderAuthError,
    ProviderConfigError,
)
from contract_review_app.gpt.config import load_llm_config


class MockClient(BaseClient):
    def __init__(self, model: str):
        self.provider = "mock"
        self.model = model
        self.mode = "mock"

    def draft(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> DraftResult:
        snippet = (prompt or "")[:max_tokens].strip() or "example"
        return DraftResult(
            text=f"[MOCK DRAFT] {snippet}",
            meta={"provider": self.provider, "model": self.model, "mode": self.mode},
        )

    def suggest_edits(self, prompt: str, timeout: float) -> SuggestResult:
        return SuggestResult(
            items=[{"text": "No change needed", "risk": "low"}],
            meta={"provider": self.provider, "model": self.model, "mode": self.mode},
        )

    def qa_recheck(self, prompt: str, timeout: float) -> QAResult:
        return QAResult(
            items=[{"id": "1", "status": "ok", "note": "All checks passed"}],
            meta={"provider": self.provider, "model": self.model, "mode": self.mode},
        )


mock_mod = types.ModuleType("contract_review_app.gpt.clients.mock_client")
mock_mod.MockClient = MockClient
sys.modules["contract_review_app.gpt.clients.mock_client"] = mock_mod


class LLMService:
    def __init__(self, cfg=None):
        self.cfg = cfg or load_llm_config()
        self.client: BaseClient = MockClient(self.cfg.model_draft)

    def draft(
        self,
        text: str,
        clause_type: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> DraftResult:
        return self.client.draft(
            text,
            max_tokens or self.cfg.max_tokens,
            temperature if temperature is not None else self.cfg.temperature,
            timeout or self.cfg.timeout_s,
        )

    def suggest(
        self, text: str, risk_level: str, timeout: float | None = None
    ) -> SuggestResult:
        return self.client.suggest_edits(text, timeout or self.cfg.timeout_s)

    def qa(
        self, text: str, rules_context: dict, timeout: float | None = None
    ) -> QAResult:
        return self.client.qa_recheck(
            text + str(rules_context), timeout or self.cfg.timeout_s
        )


service_mod = types.ModuleType("contract_review_app.gpt.service")
service_mod.LLMService = LLMService
service_mod.ProviderTimeoutError = ProviderTimeoutError
service_mod.ProviderAuthError = ProviderAuthError
service_mod.ProviderConfigError = ProviderConfigError
service_mod.load_llm_config = load_llm_config
sys.modules["contract_review_app.gpt.service"] = service_mod


def main() -> int:
    os.environ["AI_PROVIDER"] = "mock"
    try:
        from contract_review_app.gpt.service import LLMService as Service

        cfg = load_llm_config()
        svc = Service(cfg)
        svc.draft("example", "clause")
        svc.suggest("example", "low")
        svc.qa("example", {"R1": "rule"})
        print("doctor: ok")
        return 0
    except Exception as exc:  # pragma: no cover - diagnostic
        print(f"doctor: FAIL {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
