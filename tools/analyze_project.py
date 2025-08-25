#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project offline analyzer for `contract_ai`.
Stdlib-only. Produces JSON + HTML reports under ./reports.
Safe to run without internet and without running servers.
"""

from __future__ import annotations
import os, sys, re, ast, json, argparse, html, textwrap
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any
import datetime
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]  # points to ./contract_ai
PROJECT = ROOT

# ------------------------- helpers -------------------------

def read_text_safe(p: Path, max_bytes: int = 2_000_000) -> str:
    try:
        data = p.read_bytes()
        if len(data) > max_bytes:
            return data[:max_bytes].decode("utf-8", "ignore")
        return data.decode("utf-8", "ignore")
    except Exception:
        return ""

def find_files(mask: str) -> List[Path]:
    return list(PROJECT.glob(mask))

def rel(p: Path) -> str:
    try:
        return str(p.relative_to(PROJECT))
    except Exception:
        return str(p)

def ast_parse_safe(code: str, filename: str) -> ast.AST | None:
    try:
        return ast.parse(code, filename=filename)
    except Exception:
        return None

def extract_imports(tree: ast.AST) -> List[str]:
    mods = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                mods.append(a.name)
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                mods.append(n.module)
    return mods

def find_fastapi_endpoints(code: str) -> Dict[str, Any]:
    # heuristic static scan: decorators like @app.get("/path"), @app.post('/x')
    endpoints = []
    cors = {"present": False, "allow_origins": None, "expose_headers": None}
    # CORS config
    cors_present = re.search(r"CORSMiddleware", code)
    if cors_present:
        cors["present"] = True
        # allow_origins
        m = re.search(r"allow_origins\s*=\s*(\[[^\]]*\]|\"[^\"]*\"|'[^']*')", code)
        cors["allow_origins"] = m.group(1) if m else None
        # expose_headers
        m = re.search(r"expose_headers\s*=\s*(\[[^\]]*\]|\"[^\"]*\"|'[^']*')", code)
        cors["expose_headers"] = m.group(1) if m else None

    # endpoints
    for m in re.finditer(r"@(?P<app>[A-Za-z_][\w]*)\.(get|post|put|patch|delete)\s*\(\s*(?P<path>r?['\"][^'\"]+['\"]).*?\)", code):
        endpoints.append({"decorator": m.group(0)[:120], "path": m.group("path"), "app_name": m.group("app")})
    return {"cors": cors, "endpoints": endpoints}

def list_rule_modules() -> Dict[str, Any]:
    base = PROJECT / "contract_review_app" / "legal_rules"
    rules_dir = base / "rules"
    py_files = list(rules_dir.glob("*.py"))
    yaml_files = list(rules_dir.glob("*.yml")) + list(rules_dir.glob("*.yaml"))
    duplicate_registry = (rules_dir / "registry.py").exists()
    # scan for forbidden import string across project
    offending = []
    for p in PROJECT.rglob("*.py"):
        t = read_text_safe(p)
        if re.search(r"legal_rules\.rules\.registry", t):
            offending.append(rel(p))
    return {
        "rules_dir": rel(rules_dir),
        "py_count": len(py_files),
        "yaml_count": len(yaml_files),
        "duplicate_registry_py": duplicate_registry,
        "offending_imports": offending,
        "py_list": [rel(x) for x in py_files][:50],
        "yaml_list": [rel(x) for x in yaml_files][:50],
    }

def analyze_manifest() -> Dict[str, Any]:
    manifest = PROJECT / "word_addin_dev" / "manifest.xml"
    if not manifest.exists():
        return {"present": False}
    try:
        tree = ET.parse(str(manifest))
        root = tree.getroot()
        ns = {"m": root.tag.split("}")[0].strip("{")}
        app_id = root.find(".//m:Id", ns)
        src = root.find(".//m:SourceLocation", ns)
        appdomains = [e.text for e in root.findall(".//m:AppDomain", ns)]
        default_url = src.attrib.get("{http://schemas.microsoft.com/office/mailappversionoverrides/1.0}DefaultValue") if src is not None else None
        # many manifests use DefaultValue attribute; fall back to text
        source_location = default_url or (src.text if src is not None else None)
        return {
            "present": True,
            "id": app_id.text if app_id is not None else None,
            "source_location": source_location,
            "app_domains": appdomains,
            "path": rel(manifest),
        }
    except Exception as e:
        return {"present": True, "error": str(e), "path": rel(manifest)}

def analyze_panel() -> Dict[str, Any]:
    out = {}
    # serve_https_panel.py rewrites
    serve = PROJECT / "word_addin_dev" / "serve_https_panel.py"
    out["serve_https_panel_py"] = {"present": serve.exists(), "path": rel(serve)}
    if serve.exists():
        t = read_text_safe(serve)
        rewrites = bool(re.search(r"/app/build-.*taskpane\.html", t)) and bool(re.search(r"/app/build-.*taskpane\.bundle\.js", t))
        out["serve_https_panel_py"]["has_rewrites"] = rewrites
    # static assets
    t_html = PROJECT / "taskpane.html"
    b_js = PROJECT / "taskpane.bundle.js"
    out["taskpane_html"] = {"present": t_html.exists(), "path": rel(t_html)}
    out["taskpane_bundle_js"] = {"present": b_js.exists(), "path": rel(b_js)}
    # certs
    certs = PROJECT / "word_addin_dev" / "certs"
    out["certs_dir"] = {"present": certs.exists(), "files": [rel(x) for x in certs.glob("*")]}
    return out

def import_graph() -> Dict[str, Any]:
    graph: Dict[str, Set[str]] = {}
    missing: Dict[str, List[str]] = {}
    py_files = list(PROJECT.rglob("*.py"))
    for p in py_files:
        modname = rel(p)
        code = read_text_safe(p)
        tree = ast_parse_safe(code, modname)
        deps: Set[str] = set()
        if tree:
            for m in extract_imports(tree):
                deps.add(m)
        graph[modname] = deps
        # mark possibly project-internal misses
        local_refs = [d for d in deps if d.startswith("contract_review_app") or d.startswith("word_addin_dev")]
        for d in local_refs:
            # try map to file existence heuristic
            parts = d.split(".")
            candidate = PROJECT.joinpath(*parts)  # module dir
            if not (candidate.with_suffix(".py").exists() or candidate.exists()):
                missing.setdefault(modname, []).append(d)
    # cycles (simple DFS on file->file is noisy); we just flag heavy importers
    heavy = sorted(graph.items(), key=lambda kv: len(kv[1]), reverse=True)[:20]
    return {"graph": {k: sorted(v) for k, v in graph.items()}, "heavy_importers": [{"file": k, "count": len(v)} for k, v in heavy], "missing_locals": missing}

def analyze_fastapi() -> Dict[str, Any]:
    app_files = []
    cors_info = []
    endpoints = []
    for p in PROJECT.rglob("*.py"):
        code = read_text_safe(p)
        if "FastAPI(" in code:  # candidate
            app_files.append(rel(p))
        info = find_fastapi_endpoints(code)
        if info["cors"]["present"]:
            cors_info.append({"file": rel(p), **info["cors"]})
        if info["endpoints"]:
            for e in info["endpoints"]:
                e["file"] = rel(p)
                endpoints.append(e)
    return {"app_files": app_files, "cors": cors_info, "endpoints": endpoints}

def analyze_env() -> Dict[str, Any]:
    keys = [k for k in os.environ.keys() if re.search(r"(OPENAI|ANTHROPIC|AZURE|OPENROUTER|LLM|MODEL|GPT)", k, re.I)]
    return {"interesting_env": {k: os.environ.get(k, "") for k in keys}}

def summarize_findings(report: Dict[str, Any]) -> Dict[str, Any]:
    issues = []

    # Rules
    r = report["rules"]
    if r["py_count"] + r["yaml_count"] == 0:
        issues.append({"severity":"fail","area":"rules","msg":"No rules found in legal_rules/rules"})
    if r["duplicate_registry_py"]:
        issues.append({"severity":"warn","area":"rules","msg":"Duplicate rules/registry.py present (may shadow root registry)"})
    if r["offending_imports"]:
        issues.append({"severity":"fail","area":"rules","msg":"Found imports of legal_rules.rules.registry","detail":r["offending_imports"]})

    # CORS
    cors = report["fastapi"]["cors"]
    if cors:
        # check for expose headers
        has_expose = any(c.get("expose_headers") for c in cors)
        if not has_expose:
            issues.append({"severity":"warn","area":"backend","msg":"CORSMiddleware present but expose_headers not found"})
    else:
        issues.append({"severity":"warn","area":"backend","msg":"FastAPI app found but no CORSMiddleware detected"})

    # Manifest / panel
    man = report["manifest"]
    if not man.get("present"):
        issues.append({"severity":"fail","area":"addin","msg":"word_addin_dev/manifest.xml not found"})
    else:
        src = man.get("source_location")
        if not src:
            issues.append({"severity":"warn","area":"addin","msg":"Manifest has no SourceLocation(DefaultValue)"})
        else:
            if not re.search(r"https://(127\.0\.0\.1|localhost):3000", src or ""):
                issues.append({"severity":"warn","area":"addin","msg":f"Manifest SourceLocation looks non-dev: {src}"})
    panel = report["panel"]
    if not panel["taskpane_html"]["present"]:
        issues.append({"severity":"warn","area":"panel","msg":"taskpane.html not found at repo root"})
    if not panel["taskpane_bundle_js"]["present"]:
        issues.append({"severity":"warn","area":"panel","msg":"taskpane.bundle.js not found at repo root"})
    if panel["serve_https_panel_py"]["present"] and not panel["serve_https_panel_py"].get("has_rewrites"):
        issues.append({"severity":"warn","area":"panel","msg":"serve_https_panel.py has no rewrite rules for /app/build-*"})
    # Env
    if not report["env"]["interesting_env"]:
        issues.append({"severity":"info","area":"llm","msg":"No LLM-related env variables detected (OK for rule-only mode)"})

    return {"issues": issues}

def render_html(report: Dict[str, Any]) -> str:
    def badge(sv): 
        return {"fail":"#dc2626","warn":"#d97706","ok":"#16a34a","info":"#2563eb"}.get(sv,"#6b7280")
    issues = report["summary"]["issues"]
    rows = []
    for it in issues:
        color = badge(it["severity"])
        detail = html.escape(json.dumps(it.get("detail", ""), ensure_ascii=False))
        rows.append(f"<tr><td><span style='background:{color};color:white;padding:2px 6px;border-radius:6px'>{it['severity'].upper()}</span></td><td>{html.escape(it['area'])}</td><td>{html.escape(it['msg'])}</td><td><code>{detail}</code></td></tr>")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>contract_ai — offline analysis</title>
<style>body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;padding:24px}} h2{{margin-top:28px}} table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ddd;padding:8px;vertical-align:top}} code{{font-family:ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap}}</style>
</head><body>
<h1>contract_ai — Offline Analysis</h1>
<p>Generated: {ts}</p>

<h2>Summary</h2>
<table><tr><th>Severity</th><th>Area</th><th>Message</th><th>Detail</th></tr>
{''.join(rows) if rows else '<tr><td colspan=4>OK — no major issues detected.</td></tr>'}
</table>

<h2>FastAPI</h2>
<pre>{html.escape(json.dumps(report["fastapi"], indent=2, ensure_ascii=False))}</pre>

<h2>Rules</h2>
<pre>{html.escape(json.dumps(report["rules"], indent=2, ensure_ascii=False))}</pre>

<h2>Word Add-in</h2>
<pre>{html.escape(json.dumps(report["manifest"], indent=2, ensure_ascii=False))}</pre>
<pre>{html.escape(json.dumps(report["panel"], indent=2, ensure_ascii=False))}</pre>

<h2>Import Graph (top heavy importers)</h2>
<pre>{html.escape(json.dumps(report["imports"]["heavy_importers"], indent=2, ensure_ascii=False))}</pre>

<h2>Interesting ENV</h2>
<pre>{html.escape(json.dumps(report["env"], indent=2, ensure_ascii=False))}</pre>

<h2>Inventory</h2>
<pre>{html.escape(json.dumps(report["inventory"], indent=2, ensure_ascii=False))}</pre>

</body></html>"""

def inventory() -> Dict[str, Any]:
    # summarize file types and key paths
    files = [p for p in PROJECT.rglob("*") if p.is_file()]
    by_ext: Dict[str, int] = {}
    for f in files:
        by_ext.setdefault(f.suffix.lower(), 0)
        by_ext[f.suffix.lower()] += 1
    key_paths = {
        "app_py": [rel(p) for p in PROJECT.rglob("app.py")],
        "orchestrator_py": [rel(p) for p in PROJECT.rglob("orchestrator.py")],
        "manifest_xml": rel(PROJECT / "word_addin_dev" / "manifest.xml"),
        "serve_https_panel_py": rel(PROJECT / "word_addin_dev" / "serve_https_panel.py"),
        "certs_dir": rel(PROJECT / "word_addin_dev" / "certs"),
        "legal_rules_dir": rel(PROJECT / "contract_review_app" / "legal_rules"),
        "rules_dir": rel(PROJECT / "contract_review_app" / "legal_rules" / "rules"),
    }
    return {"total_files": len(files), "by_ext": by_ext, "key_paths": key_paths}

def main():
    ap = argparse.ArgumentParser(description="Offline analyzer for contract_ai")
    ap.add_argument("--project-root", default=str(PROJECT), help="Path to project root (default: script/../)")
    ap.add_argument("--out", default=str(PROJECT / "reports"), help="Output directory for reports")
    args = ap.parse_args()

    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {}
    report["project_root"] = str(PROJECT)
    report["inventory"] = inventory()
    report["imports"] = import_graph()
    report["fastapi"] = analyze_fastapi()
    report["rules"] = list_rule_modules()
    report["manifest"] = analyze_manifest()
    report["panel"] = analyze_panel()
    report["env"] = analyze_env()
    report["summary"] = summarize_findings(report)

    # write JSON
    json_path = outdir / "analysis.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # write HTML
    html_path = outdir / "analysis.html"
    html_path.write_text(render_html(report), encoding="utf-8")

    print(f"[OK] Report written:\n  JSON: {json_path}\n  HTML: {html_path}")

if __name__ == "__main__":
    main()
