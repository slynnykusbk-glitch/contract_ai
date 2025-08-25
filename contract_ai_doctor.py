#!/usr/bin/env python3
from __future__ import annotations

"""Contract AI — Doctor v2.

End-to-end diagnostics across: Front (manifest+taskpane), Network/TLS/CORS,
Backend, Pipeline, Rules, Response shape. Outputs markdown+json with a
stage-by-stage chain view and suggested fixes.
"""

import argparse
import json
import os
import re
import socket
import ssl
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional HTTP client
try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning

    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
except Exception:
    requests = None

OK = "PASS"
WARN = "WARN"
FAIL = "FAIL"

@dataclass
class Check:
    section: str
    name: str
    status: str
    details: str = ""
    data: Optional[dict] = None
    ms: Optional[int] = None

def add(report: List[Check], section: str, status: str, name: str, details: str, data: Optional[dict] = None, ms: Optional[int] = None):
    report.append(Check(section=section, name=name, status=status, details=details, data=data, ms=ms))

def now_ms() -> int:
    return int(time.time() * 1000)

# --------------------------- TLS / Cert inspection ---------------------------
def inspect_cert(host: str, port: int, timeout: float = 4.0) -> Tuple[bool, Dict[str, Any], str]:
    info: Dict[str, Any] = {}
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                info["subject"] = cert.get("subject")
                info["issuer"] = cert.get("issuer")
                info["notBefore"] = cert.get("notBefore")
                info["notAfter"] = cert.get("notAfter")
                return True, info, "cert retrieved"
    except Exception as e:
        return False, info, f"cert error: {e!r}"

# --------------------------- HTTP helpers -----------------------------------
def http_get(url: str, headers: dict | None = None, timeout: float = 8.0) -> Tuple[bool, int, dict, str, int]:
    if not requests:
        return False, 0, {}, "requests missing", 0
    t0 = now_ms()
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout, verify=False)
        ms = now_ms() - t0
        try:
            j = r.json()
        except Exception:
            j = {"raw": r.text[:1000]}
        return r.ok, r.status_code, j, "", ms
    except Exception as e:
        return False, 0, {}, repr(e), now_ms() - t0

def http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = 12.0) -> Tuple[bool, int, dict, str, int]:
    if not requests:
        return False, 0, {}, "requests missing", 0
    t0 = now_ms()
    try:
        r = requests.post(url, json=payload, headers=headers or {}, timeout=timeout, verify=False)
        ms = now_ms() - t0
        try:
            j = r.json()
        except Exception:
            j = {"raw": r.text[:1000]}
        return r.ok, r.status_code, j, "", ms
    except Exception as e:
        return False, 0, {}, repr(e), now_ms() - t0

def http_options(url: str, origin: str, req_method: str = "POST", timeout: float = 6.0) -> Tuple[bool, int, dict, str, int]:
    if not requests:
        return False, 0, {}, "requests missing", 0
    t0 = now_ms()
    try:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": req_method,
            "Access-Control-Request-Headers": "content-type"
        }
        r = requests.options(url, headers=headers, timeout=timeout, verify=False)
        ms = now_ms() - t0
        hdr = {k.lower(): v for k, v in r.headers.items()}
        return (r.ok and ("access-control-allow-origin" in hdr)), r.status_code, hdr, "", ms
    except Exception as e:
        return False, 0, {}, repr(e), now_ms() - t0

# --------------------------- Static parsers ----------------------------------
def parse_manifest(path: Path) -> Dict[str, Any]:
    out = {"ok": False, "source_location": None, "cache_bust": False, "hosts": []}
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'<SourceLocation[^>]*DefaultValue="([^"]+)"', txt, re.IGNORECASE)
        if m:
            out["source_location"] = m.group(1)
            out["cache_bust"] = ("?v=" in out["source_location"])
        out["hosts"] = re.findall(r'<Host\s+Name="([^"]+)"', txt, re.IGNORECASE)
        out["ok"] = bool(m)
    except Exception:
        out["ok"] = False
    return out

def check_taskpane_files(webroot: Path) -> Dict[str, Any]:
    html = webroot / "taskpane.html"
    js = webroot / "taskpane.bundle.js"
    res = {"exists": html.exists() and js.exists(), "html": str(html), "js": str(js), "containers": {}, "backend_hint": None}
    if not res["exists"]:
        return res
    try:
        h = html.read_text(encoding="utf-8", errors="ignore")
        res["containers"] = {
            "resClauseType": ("resClauseType" in h),
            "findingsList": ("findingsList" in h),
            "recsList": ("recsList" in h),
            "rawJson": ("rawJson" in h),
        }
    except Exception:
        pass
    try:
        j = js.read_text(encoding="utf-8", errors="ignore")
        # Very rough fetch/URL sniff
        m = re.search(r'https?://localhost:\d{3,5}', j)
        res["backend_hint"] = m.group(0) if m else None
        res["has_render_fn"] = ("renderAnalysis" in j)
    except Exception:
        res["backend_hint"] = None
        res["has_render_fn"] = False
    return res

# --------------------------- Rules & pipeline (local imports) ----------------
def _to_dict(obj):
    for m in ("model_dump", "dict", "_asdict"):
        if hasattr(obj, m):
            try:
                return getattr(obj, m)()
            except Exception:
                pass
    if isinstance(obj, dict):
        return obj
    try:
        return dict(obj)
    except Exception:
        return {"_repr": repr(obj)}

def discover_rules_pkg() -> Tuple[Dict[str, Any], str]:
    """
    Бери список правил із реального пайплайна, а не через прямий pkg scan.
    Так ми отримуємо ту саму картину, що й бекенд/health.
    """
    try:
        import importlib
        pipe = importlib.import_module("contract_review_app.engine.pipeline")
        rules = pipe.discover_rules()  # type: ignore[attr-defined]
        if isinstance(rules, dict) and rules:
            # перетворюємо у {name: callable}, джерело — pipeline
            return rules, "pipeline.discover_rules"
    except Exception:
        pass
    return {}, ""

def run_rule(fn, rule_name: str, text: str) -> Tuple[bool, Dict[str, Any], str]:
    try:
        try:
            from contract_review_app.core.schemas import AnalysisInput  # type: ignore
            inp = AnalysisInput(clause_type=rule_name, text=text)
        except Exception:
            inp = {"clause_type": rule_name, "text": text}
        out = fn(inp)
        out = _to_dict(out)
        ok = isinstance(out, dict) and isinstance(out.get("findings", []), list)
        return ok, out if isinstance(out, dict) else {}, f"status={out.get('status','?')} find={len(out.get('findings',[])) if isinstance(out,dict) else 'n/a'}"
    except Exception as e:
        return False, {}, f"exception: {e!r}"

def pipeline_sanity(text: str) -> Tuple[bool, Dict[str, Any], str]:
    try:
        import importlib
        pipe = importlib.import_module("contract_review_app.engine.pipeline")
        res = pipe.analyze_document(text)  # type: ignore
        ok = bool((res.get("results") or {}))
        names = list((res.get("results") or {}).keys())
        return ok, res, f"results={names[:5]}"
    except Exception as e:
        return False, {}, f"exception: {e!r}"

# --------------------------- Doctor main -------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Contract AI — Doctor v2")
    ap.add_argument("--backend", help="Backend base URL, e.g. https://localhost:9000")
    ap.add_argument("--front", help="Frontend root URL, e.g. https://localhost:3000")
    ap.add_argument("--manifest", help="Path to manifest.xml")
    ap.add_argument("--webroot", help="Path to folder with taskpane.html/taskpane.bundle.js")
    ap.add_argument("--app", help="Path to backend app.py (for CORS scan)")
    ap.add_argument("--out", default="doctor_report")
    args = ap.parse_args()

    report: List[Check] = []
    meta = {"python": sys.version, "cwd": os.getcwd()}

    # 0) Front static (manifest + taskpane)
    if args.manifest and os.path.exists(args.manifest):
        m = parse_manifest(Path(args.manifest))
        status = OK if m["ok"] and (args.front is None or str(m["source_location"]).startswith(args.front)) else WARN if m["ok"] else FAIL
        add(
            report,
            "FRONT",
            status,
            "Manifest SourceLocation",
            f"url={m['source_location']} cache_bust={'yes' if m['cache_bust'] else 'no'} hosts={','.join(m['hosts'])}",
            m,
        )
    else:
        add(report, "FRONT", WARN, "Manifest", "Path not provided or not found. (--manifest)")

    if args.webroot and os.path.exists(args.webroot):
        tp = check_taskpane_files(Path(args.webroot))
        need = [k for k,v in tp.get("containers",{}).items() if not v]
        has = tp.get("has_render_fn", False)
        st = OK if tp["exists"] and not need and has else FAIL if not tp["exists"] else WARN
        add(
            report,
            "FRONT",
            st,
            "Taskpane files",
            f"exists={tp['exists']} containers-missing={need} "
            f"render_fn={'ok' if has else 'absent'} backend_hint={tp.get('backend_hint')}",
            tp,
        )
    else:
        add(report, "FRONT", FAIL, "Taskpane files", f"Missing {args.webroot}\\taskpane.html or ...bundle.js")

    # 1) Network/TLS/CORS
    if args.backend:
        # TLS cert info
        try:
            m = re.match(r'^https?://([^/:]+):?(\d+)?', args.backend.strip())
            host = m.group(1) if m else "localhost"
            port = int(m.group(2)) if (m and m.group(2)) else (443 if args.backend.startswith("https") else 80)
        except Exception:
            host, port = "localhost", 443
        okc, cert, msg = inspect_cert(host, port)
        add(report, "NET", OK if okc else WARN, "TLS certificate", msg, cert)

        # Health
        ok, sc, j, err, ms = http_get(args.backend.rstrip("/") + "/health")
        add(report, "NET", OK if ok else FAIL, "Health endpoint", f"{sc if sc else ''} {err}", j, ms)

        # CORS preflight
        if args.front:
            okp, scp, hdr, errp, msp = http_options(args.backend.rstrip("/") + "/api/analyze", origin=args.front)
            allow = hdr.get("access-control-allow-origin")
            st = OK if okp and allow in (args.front, '*') else WARN if scp else FAIL
            add(report, "NET", st, "CORS preflight", f"status={scp} allow-origin={allow}", hdr, msp)
    else:
        add(report, "NET", WARN, "Backend URL", "Not provided (--backend)")

    # 2) Backend / API behaviour
    # emulate panel call with x-cid + invariants
    cid = f"cid-{int(time.time())}"
    payload = {"text": "The Receiving Party shall keep Confidential Information secret and not disclose to third parties.", "clause_type": None}
    headers = {"x-cid": cid, "content-type": "application/json"}
    if args.backend:
        ok, sc, j, err, ms = http_post_json(args.backend.rstrip("/") + "/api/analyze", payload, headers=headers)
        inv = []
        if ok:
            # invariants
            if not (j.get("findings") or (j.get("analysis",{}).get("findings")) or (j.get("results"))):
                inv.append("empty-findings")
            allowed_types = (
                None,
                "confidentiality",
                "definitions",
                "termination",
                "indemnity",
                "governing_law",
                "jurisdiction",
                "force_majeure",
                "unknown",
            )
            if j.get("clause_type") not in allowed_types:
                inv.append("bad-clause-type")
        add(
            report,
            "API",
            OK if ok and not inv else FAIL,
            "POST /api/analyze",
            f"http={sc} inv={','.join(inv) if inv else 'ok'} {err}",
            {"keys": list(j.keys())[:12] if j else []},
            ms,
        )

        # try server-side trace if available
        if requests:
            okt, sct, jt, errt, mst = http_get(args.backend.rstrip("/") + f"/api/trace/{cid}")
            add(report, "API", OK if okt else WARN, "Trace by CID", f"{sct} {errt}", jt, mst)

    # 3) Rules discovery + runtime
    rules, pkgname = discover_rules_pkg()
    add(report, "RULES", OK if rules else FAIL, "Rules discovery", f"{len(rules)} module(s) in {pkgname}", {"rules": sorted(list(rules.keys()))})
    samples = {
        "confidentiality": "The Receiving Party shall keep Confidential Information secret and not disclose to third parties.",
        "definitions": "Definitions and Interpretation: “Agreement” means this contract; “Party” means each signatory.",
        "termination": "Either party may terminate for material breach with 30 days' written notice.",
        "indemnity": "Each party shall indemnify the other from and against all claims arising from breach.",
        "governing_law": "This Agreement shall be governed by and construed in accordance with the laws of England and Wales.",
        "jurisdiction": "The courts of England shall have exclusive jurisdiction to settle any disputes.",
        "force_majeure": "Neither party shall be liable for delay due to events of force majeure beyond its control.",
    }
    for rname, fn in rules.items():
        ok, out, info = run_rule(fn, rname, samples.get(rname, "Sample text for rule execution smoke test."))
        add(report, "RULES", OK if ok else FAIL, f"Rule run: {rname}", info, {"out_keys": list(out.keys())[:12] if out else []})

    # 4) Pipeline sanity
    okp, pres, pinfo = pipeline_sanity(samples["confidentiality"])
    add(report, "PIPELINE", OK if okp else FAIL, "pipeline.analyze_document", pinfo, {"result_keys": list((pres.get('results') or {}).keys()) if pres else []})

    # Aggregate & write
    data = {
        "meta": meta,
        "summary": {
            "PASS": sum(1 for c in report if c.status == OK),
            "WARN": sum(1 for c in report if c.status == WARN),
            "FAIL": sum(1 for c in report if c.status == FAIL),
        },
        "checks": [asdict(c) for c in report],
        "chain_view": [
            {"stage":"Word ➜ Taskpane UI", "status":"depends on FRONT:Manifest/Taskpane checks"},
            {"stage":"Taskpane fetch ➜ Backend", "status":"depends on NET:Health/CORS + API:POST /api/analyze"},
            {"stage":"Backend router ➜ Pipeline", "status":"see PIPELINE check"},
            {"stage":"Pipeline ➜ Rules", "status":"see RULES discovery & Rule run checks"},
            {"stage":"Backend ➜ JSON", "status":"see API invariants"},
            {"stage":"Taskpane ➜ Render", "status":"FRONT:Taskpane containers + renderAnalysis() present"},
        ]
    }

    out_prefix = args.out
    Path(out_prefix).parent.mkdir(parents=True, exist_ok=True)
    json_path = f"{out_prefix}.json"
    md_path = f"{out_prefix}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    def fmt_row(c: Check) -> str:
        icon = "✅" if c.status == OK else ("⚠️" if c.status == WARN else "❌")
        ms = f" ({c.ms} ms)" if c.ms is not None else ""
        return f"| {icon} {c.status} | **{c.section}** | {c.name} | {c.details}{ms} |"

    md = []
    md.append("# Contract AI — Doctor Report v2")
    md.append("")
    md.append(f"**PASS:** {data['summary']['PASS']}  **WARN:** {data['summary']['WARN']}  **FAIL:** {data['summary']['FAIL']}")
    md.append("")
    md.append("## Chain view (end‑to‑end)")
    for s in data["chain_view"]:
        md.append(f"- **{s['stage']}** — {s['status']}")
    md.append("")
    md.append("## Checks")
    md.append("| Status | Section | Check | Details |")
    md.append("|---|---|---|---|")
    for c in report:
        md.append(fmt_row(c))

    md.append("")
    md.append("## Hints")
    md.append("- If **NET/Health** fails → backend is not listening or TLS mismatch.")
    md.append("- If **NET/CORS** warns → check CORSMiddleware allow_origins for http/https localhost:3000.")
    md.append("- If **API invariants** fail → shape mismatch: ensure /api/analyze returns findings/recommendations.")
    md.append("- If **RULES run** fails for a rule → examine that module's `analyze()` and return dict/Pydantic with `.model_dump()`.")
    md.append(
        "- If **FRONT/Taskpane** fails → ensure `taskpane.html` has containers "
        "(resClauseType, findingsList, recsList, rawJson) and JS has `renderAnalysis()`."
    )
    md.append("- Use **CID** header (`x-cid`) in panel fetch and GET `/api/trace/{cid}` for server-side trace (if middleware present).")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"[OK] Wrote {md_path} and {json_path}")

if __name__ == "__main__":
    main()
