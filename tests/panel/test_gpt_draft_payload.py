import json
import os
import urllib.request

BASE = os.environ.get("PANEL_BASE", "https://localhost:9443")

def _post(path, payload):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"},
        method="POST"
    )
    return urllib.request.urlopen(req, timeout=5)

def test_gpt_draft_accepts_before_after():
    payload = {"text":"Ping", "mode":"friendly", "before_text":"", "after_text":""}
    with _post("/api/gpt-draft", payload) as r:
        assert r.status == 200
