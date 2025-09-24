import logging
from contract_review_app.api.models import SCHEMA_VERSION


def test_learning_log_write_error(api, monkeypatch, caplog):
    monkeypatch.setenv("API_KEY", "secret")
    headers = {"x-api-key": "secret", "x-schema-version": SCHEMA_VERSION}

    def fail_write(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr("contract_review_app.api.app.secure_write", fail_write)
    with caplog.at_level(logging.WARNING, logger="contract_ai"):
        resp = api.post("/api/learning/log", json={"foo": "bar"}, headers=headers)
    assert resp.status_code == 204
    assert resp.headers.get("x-learning-log-status") == "error"
    messages = [record.getMessage() for record in caplog.records]
    assert any("failed to write learning log" in m for m in messages)
