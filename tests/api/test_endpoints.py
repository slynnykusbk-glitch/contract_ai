import os
import sys
import types
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
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


# patch GPT service and orchestrator before importing the app
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

orch_mod = types.ModuleType("contract_review_app.api.orchestrator")


async def run_analyze(model):
    return {
        "analysis": {"issues": ["dummy"]},
        "results": {},
        "clauses": [],
        "document": {"text": model.text},
    }


dummy_async = lambda *a, **k: None
orch_mod.run_analyze = run_analyze
orch_mod.run_qa_recheck = dummy_async
orch_mod.run_gpt_draft = dummy_async
orch_mod.run_suggest_edits = dummy_async
sys.modules["contract_review_app.api.orchestrator"] = orch_mod

os.environ["AI_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    for key in ("schema", "rules_count", "llm"):
        assert key in data


def test_analyze_endpoint():
    r = client.post("/api/analyze", json={"text": "hello"})
    assert r.status_code == 200
    issues = r.json().get("analysis", {}).get("issues", [])
    assert isinstance(issues, list) and issues


def test_summary_endpoint():
    r = client.post("/api/summary", json={"text": "hello"})
    assert r.status_code == 200
    assert r.json().get("summary")


def test_gpt_draft_endpoint():
    r = client.post(
        "/api/gpt/draft", json={"text": "sample", "clause_type": "clause"}
    )
    assert r.status_code == 200
    assert r.json().get("draft_text")


def test_suggest_edits_endpoint():
    r = client.post("/api/suggest_edits", json={"text": "sample"})
    assert r.status_code == 200
    items = r.json().get("suggestions")
    assert isinstance(items, list)


def test_qa_recheck_endpoint():
    payload = {"text": "hi", "rules": {"R1": "rule"}}
    r = client.post("/api/qa-recheck", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data.get("issues") == []
    assert data.get("analysis", {}).get("ok") is True


def test_calloff_validate_endpoint():
    payload = {
        "term": "12",
        "description": "desc",
        "price": "1",
        "currency": "USD",
        "vat": "1",
        "delivery_point": "A",
        "representatives": "J",
        "notices": "N",
        "po_number": "P",
        "subcontracts": False,
        "scope_altered": False,
    }
    r = client.post("/api/calloff/validate", json=payload)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
