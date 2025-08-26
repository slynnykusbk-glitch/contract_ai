import json, subprocess, sys


def _run_doctor(tmp_path, monkeypatch):
    out_dir = tmp_path / "diag"
    out_dir.mkdir()
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock")
    monkeypatch.setenv("LLM_TIMEOUT", "5")
    cmd = [sys.executable, "tools/doctor.py", "--out", str(out_dir), "--json"]
    assert subprocess.call(cmd) == 0
    return json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))


def test_app_has_analyze_hook(monkeypatch):
    import contract_review_app.api.app as app_mod

    assert hasattr(app_mod, "_analyze_document")

    def fake(text: str):
        return {"status": "OK", "findings": [{"id": "X"}], "summary": {"len": len(text)}}

    monkeypatch.setattr(app_mod, "_analyze_document", fake, raising=True)

    # перевіримо, що ендпоїнт існує у маршрутах
    from contract_review_app.api.app import app

    assert any(getattr(r, "path", None) == "/api/analyze" for r in app.routes)


def test_doctor_reports_analyze_hook(tmp_path, monkeypatch):
    data = _run_doctor(tmp_path, monkeypatch)
    assert data["api"]["has__analyze_document"] is True
