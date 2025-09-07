from fastapi.testclient import TestClient
from contract_review_app.api.app import app

client = TestClient(app)

def analyze_and_render(text: str) -> str:
    resp = client.post("/api/analyze", json={"text": text})
    assert resp.status_code == 200
    data = resp.json()
    out = []
    for f in data["analysis"]["findings"]:
        sev = str(f.get("severity", "")).upper()
        rid = f.get("rule_id", "")
        snippet = f.get("snippet", "")
        advice = f.get("advice", "")
        law = "; ".join(f.get("law_refs", []))
        conflict = "; ".join(f.get("conflict_with", []))
        fix = f.get("suggestion", {}).get("text", "") if isinstance(f.get("suggestion"), dict) else ""
        out.append(f"[{sev}] {rid} {snippet}\nReason: {advice}\nLaw: {law}\nConflict: {conflict}\nSuggested fix: {fix}")
    return "\n\n".join(out)
