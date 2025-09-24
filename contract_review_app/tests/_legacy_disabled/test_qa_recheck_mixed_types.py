import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api import orchestrator

client = TestClient(app)


class Obj:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _fake_doc():
    finding_obj = Obj(code="OBJ", message="o-msg", severity="low")
    analysis_obj = Obj(
        clause_type="obj", risk_level="medium", score=1, findings=[finding_obj]
    )
    analysis_dict = {
        "clause_type": "dict",
        "risk_level": "high",
        "score": 2,
        "findings": [{"code": "D", "message": "d-msg", "severity": "high"}],
    }
    return Obj(
        summary_risk="medium",
        summary_score=0,
        summary_status="OK",
        analyses=[analysis_dict, analysis_obj],
    )


def test_qa_recheck_mixed_dict_and_object(monkeypatch):
    def fake_analyze_document(text):
        return _fake_doc()

    monkeypatch.setattr(
        orchestrator, "_engine", SimpleNamespace(analyze_document=fake_analyze_document)
    )
    body = {"text": "Hello", "applied_changes": []}
    r = client.post("/api/qa-recheck", content=json.dumps(body))
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert isinstance(j.get("residual_risks"), list)
    assert len(j["residual_risks"]) == 1
