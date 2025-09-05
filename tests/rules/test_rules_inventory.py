from pathlib import Path
from fastapi.testclient import TestClient
from contract_review_app.api.app import app


client = TestClient(app)


def test_rules_inventory_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    meta_rules = data.get("meta", {}).get("rules", [])
    paths = [m.get("path", "") for m in meta_rules]
    assert any(p.startswith("contract_review_app/legal_rules/policy_packs") for p in paths)
    assert any(p.startswith("core/rules") for p in paths)

    policy_dir = Path("contract_review_app/legal_rules/policy_packs")
    core_dir = Path("core/rules")
    yaml_files = list(policy_dir.glob("*.yaml")) + list(core_dir.rglob("*.yaml"))

    assert len(meta_rules) >= len(yaml_files)
    assert data.get("rules_count", 0) >= len(yaml_files)
