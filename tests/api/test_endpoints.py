import os
import pathlib
import sys
import types
import importlib
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from contract_review_app.gpt.config import load_llm_config
from contract_review_app.gpt.interfaces import (
    BaseClient,
    DraftResult,
    ProviderAuthError,
    ProviderConfigError,
    ProviderTimeoutError,
    QAResult,
    SuggestResult,
)


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
    text = model.text
    segments = []
    if text:
        has_lat = any("a" <= ch.lower() <= "z" for ch in text)
        has_cyr = any(ord(ch) >= 0x0400 for ch in text)
        if has_lat:
            segments.append({"lang": "latin"})
        if has_cyr:
            segments.append({"lang": "cyrillic"})
    return {
        "analysis": {"issues": ["dummy"], "segments": segments},
        "results": {},
        "clauses": [],
        "document": {"text": text},
    }


def dummy_async(*a, **k):
    return None


orch_mod.run_analyze = run_analyze
orch_mod.run_qa_recheck = dummy_async
orch_mod.run_gpt_draft = dummy_async
orch_mod.run_suggest_edits = dummy_async
sys.modules["contract_review_app.api.orchestrator"] = orch_mod

os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from contract_review_app.api.app import app  # noqa: E402
from contract_review_app.api.models import SCHEMA_VERSION  # noqa: E402

client = TestClient(app, headers={"x-schema-version": SCHEMA_VERSION})


def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    for key in ("schema", "rules_count", "llm"):
        assert key in data


def test_analyze_endpoint():
    r = client.post("/api/analyze?debug=1", json={"text": "hello"})
    assert r.status_code == 200
    data = r.json()
    issues = data.get("analysis", {}).get("issues", [])
    assert isinstance(issues, list)
    findings = data.get("analysis", {}).get("findings", [])
    assert isinstance(findings, list)

    def _ok(f):
        keys = set(f.keys())
        return (
            {"span", "text", "lang"}.issubset(keys)
            or {"start", "end"}.issubset(keys)
            or {"rule_id", "message"}.intersection(keys)
        )

    assert all(_ok(f) for f in findings)


def test_analyze_segments_with_flag(monkeypatch):
    monkeypatch.setenv("CONTRACTAI_INTAKE_NORMALIZE", "1")
    r = client.post("/api/analyze", json={"text": "hello АБВ"})
    assert r.status_code == 200
    data = r.json()
    assert "analysis" in data


def test_analyze_x_cid_deterministic():
    payload = {"text": "same"}
    r1 = client.post("/api/analyze", json=payload)
    r2 = client.post("/api/analyze", json=payload)
    assert r1.headers["x-cid"] == r2.headers["x-cid"]


def test_summary_endpoint():
    r_analyze = client.post("/api/analyze", json={"text": "hello"})
    assert r_analyze.status_code == 200
    cid = r_analyze.headers.get("x-cid")
    assert cid
    r = client.post("/api/summary", json={"cid": cid})
    assert r.status_code == 200
    assert r.json().get("summary")


def test_gpt_draft_endpoint():
    r_an = client.post("/api/analyze", json={"text": "sample"})
    cid = r_an.headers.get("x-cid")
    r = client.post("/api/gpt-draft", json={"clause_id": cid, "text": "sample"})
    assert r.status_code == 200


def test_suggest_edits_endpoint():
    r = client.post("/api/suggest_edits", json={"text": "sample"})
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok"
    assert "proposed_text" in out


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


@pytest.mark.xfail(reason="rule engine error not triggered yet when PyYAML missing")
def test_analyze_endpoint_yaml_missing(monkeypatch):
    import contract_review_app.api.app as app_mod
    import yaml

    monkeypatch.setitem(sys.modules, "yaml", None)
    importlib.reload(app_mod)
    tmp_client = TestClient(app_mod.app, headers={"x-schema-version": SCHEMA_VERSION})
    resp = tmp_client.post("/api/analyze", json={"text": "hi"})
    assert resp.status_code == 503
    data = resp.json()
    assert data.get("error_code") == "rule_engine_unavailable"
    sys.modules["yaml"] = yaml
    importlib.reload(app_mod)
