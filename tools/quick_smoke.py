import os
import time
import requests

BACKEND = os.environ.get("BACKEND_URL", "https://127.0.0.1:9443")
VERIFY  = os.environ.get("BACKEND_TLS_VERIFY", "0") == "1"

def analyze_sample():
    url = f"{BACKEND}/api/analyze"
    payload = {"text": "CONFIDENTIALITY AGREEMENT\n\nGoverning law: England and Wales.\nPayment terms: 30 days.\n"}
    r = requests.post(url, json=payload, verify=VERIFY)
    r.raise_for_status()
    data = r.json()
    cid = data.get("cid") or data.get("meta", {}).get("cid")
    print(f"[quick_smoke] analyze OK, cid={cid}")
    return cid

def get_trace(cid: str):
    url = f"{BACKEND}/api/trace/{cid}"
    r = requests.get(url, verify=VERIFY)
    r.raise_for_status()
    data = r.json()
    keys = list(data.keys())
    print(f"[quick_smoke] trace OK, sections={keys}")
    cov = data.get("coverage", {})
    print(f"[quick_smoke] coverage: total={cov.get('zones_total')} present={cov.get('zones_present')} fired={cov.get('zones_fired')}")
    return data

if __name__ == "__main__":
    cid = analyze_sample()
    time.sleep(0.3)
    get_trace(cid)
    print("[quick_smoke] done.")
