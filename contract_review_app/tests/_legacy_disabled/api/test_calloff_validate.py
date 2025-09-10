from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)


def test_calloff_validate_ok():
    payload = {
        "term": "12 months",
        "description": "Supply of goods",
        "price": "1000",
        "currency": "USD",
        "vat": "20%",
        "delivery_point": "Warehouse A",
        "representatives": "John Doe",
        "notices": "Main Street",
        "po_number": "PO123",
        "subcontracts": False,
        "scope_altered": False,
    }
    r = client.post("/api/calloff/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert isinstance(data.get("issues"), list)
    assert len(data["issues"]) == 0


def test_calloff_validate_with_issues():
    payload = {
        "description": "[●]",
        "currency": "USD",
        "delivery_point": "Port",
        "representatives": "",
        "notices": "",
        "po_number": "",
        "subcontracts": True,
        "subcontractors": [],
        "scope_altered": True,
    }
    r = client.post("/api/calloff/validate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    issues = data.get("issues") or []
    assert len(issues) > 0
    assert any(i.get("id") == "calloff_placeholders_forbidden" for i in issues)
