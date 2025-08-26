def test_app_has_analyze_hook(monkeypatch):
    import contract_review_app.api.app as app_mod
    assert hasattr(app_mod, "_analyze_document")

    def fake(text: str):
        return {"status": "OK", "findings": [{"id": "X"}], "summary": {"len": len(text)}}

    monkeypatch.setattr(app_mod, "_analyze_document", fake, raising=True)

    # перевіримо, що ендпоїнт існує у маршрутах
    from contract_review_app.api.app import app
    assert any(getattr(r, "path", None) == "/api/analyze" for r in app.routes)
