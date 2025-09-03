import httpx
import ssl


def _client():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return httpx.Client(verify=False, base_url="https://localhost:9443")


def test_health_ok():
    r = _client().get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status", "").lower() == "ok"


def test_panel_assets_served():
    c = _client()
    r1 = c.get("/panel/app/assets/api-client.js")
    r2 = c.get("/panel/app/assets/store.js")
    assert r1.status_code == 200 and len(r1.text) > 50
    assert r2.status_code == 200 and len(r2.text) > 10
