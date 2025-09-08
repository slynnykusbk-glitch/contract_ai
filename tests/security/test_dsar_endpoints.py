import json
from importlib import reload

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from contract_review_app.security import secure_store


def _get_client(tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("CR_ATREST_KEY", key)
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("FEATURE_REQUIRE_API_KEY", "1")
    monkeypatch.setenv("CONTRACTAI_RATE_PER_MIN", "1")
    import contract_review_app.api.limits as limits_mod
    reload(limits_mod)
    import contract_review_app.api.dsar as dsar_module
    reload(dsar_module)
    dsar_module._DATA_DIR = tmp_path
    secure_store.secure_write(tmp_path / "user@example.com.json", json.dumps({"audit": ["ok"]}))
    import contract_review_app.api.app as app_module
    reload(app_module)
    return TestClient(app_module.app)


def test_dsar_endpoints(tmp_path, monkeypatch):
    client = _get_client(tmp_path, monkeypatch)
    params = {"identifier": "user@example.com", "token": "t"}
    # missing api key
    assert client.get("/api/dsar/access", params=params).status_code == 401
    headers = {"x-api-key": "secret"}
    r = client.get("/api/dsar/access", params=params, headers=headers)
    assert r.status_code == 200
    assert "user@example.com" not in r.text
    # rate limit triggered on second call
    r2 = client.get("/api/dsar/access", params=params, headers=headers)
    assert r2.status_code == 429
    # erasure
    r3 = client.post("/api/dsar/erasure", params=params, headers=headers)
    assert r3.status_code == 200
    assert not (tmp_path / "user@example.com.json").exists()
    # export after deletion -> 404
    r4 = client.get("/api/dsar/export", params=params, headers=headers)
    assert r4.status_code == 404
