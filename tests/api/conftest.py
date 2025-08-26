import contract_review_app.api.app as app_mod
import pytest


@pytest.fixture(autouse=True)
def patch_analyze(monkeypatch):
    def fake(text: str):
        return {
            "analysis": {"issues": ["dummy"]},
            "results": {},
            "clauses": [],
            "document": {"text": text},
        }

    monkeypatch.setattr(app_mod, "_analyze_document", fake, raising=True)
    yield
