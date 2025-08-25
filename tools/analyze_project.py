#!/usr/bin/env python3
from __future__ import annotations

"""Offline repository analyzer for contract_ai (v2).
Generates JSON and HTML reports summarising backend, LLM, rule engine
and Word add‑in readiness. Designed for one‑click execution via PowerShell.
"""

import argparse
import ast
import asyncio
import datetime as _dt
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:  # optional dependency
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
IGNORE_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".cache",
    "__pycache__",
}
IGNORE_SUFFIXES = {".pyc", ".map"}
INCLUDE_DIRS = {"contract_review_app", "word_addin_dev", "tools"}
INCLUDE_ROOT_FILES = {
    "contract_ai_doctor.py",
    "serve_https_panel.py",
    "gen_dev_certs.py",
    "run_analysis.ps1",
}
REQUIRED_EXPOSE_HEADERS = {"x-cid", "x-cache", "x-schema-version", "x-latency-ms"}
ENV_PATTERNS = [
    "OPENAI_API_KEY",
    "OPENAI_BASE",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "AI_PROVIDER",
]

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def utc_timestamp() -> str:
    return _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)

def is_ignored(path: Path) -> bool:
    if any(part in IGNORE_DIRS for part in path.parts):
        return True
    if path.suffix in IGNORE_SUFFIXES:
        return True
    return False

def iter_included_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for d in INCLUDE_DIRS:
        p = root / d
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file() and not is_ignored(f):
                files.append(f)
    for name in INCLUDE_ROOT_FILES:
        f = root / name
        if f.exists() and f.is_file():
            files.append(f)
    return files

# ---------------------------------------------------------------------------
# backend analysis
# ---------------------------------------------------------------------------

def _extract_string(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def analyze_cors(app_path: Path) -> Dict[str, Any]:
    cors: Dict[str, Any] = {
        "allow_origins": [],
        "allow_credentials": None,
        "allow_methods": None,
        "allow_headers": None,
        "expose_headers": [],
    }
    try:
        text = app_path.read_text(encoding="utf-8", errors="ignore").lstrip("\ufeff")
        tree = ast.parse(text)
    except Exception:
        return cors
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "CORSMiddleware":
            for kw in node.keywords:
                if kw.arg in cors:
                    val = kw.value
                    if isinstance(val, (ast.List, ast.Tuple)):
                        cors[kw.arg] = [_extract_string(e) for e in val.elts if _extract_string(e)]
                    else:
                        s = _extract_string(val)
                        if s:
                            cors[kw.arg] = [s]
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.attr == "add_middleware"
        ):
            if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "CORSMiddleware":
                for kw in node.keywords:
                    if kw.arg in cors:
                        val = kw.value
                        if isinstance(val, (ast.List, ast.Tuple)):
                            cors[kw.arg] = [_extract_string(e) for e in val.elts if _extract_string(e)]
                        else:
                            s = _extract_string(val)
                            if s:
                                cors[kw.arg] = [s]
    return cors


def analyze_endpoints(api_dir: Path) -> List[Dict[str, Any]]:
    endpoints: List[Dict[str, Any]] = []
    for file in api_dir.glob("*.py"):
        try:
            text = file.read_text(encoding="utf-8", errors="ignore").lstrip("\ufeff")
            tree = ast.parse(text)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        method = dec.func.attr.upper()
                        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"}:
                            continue
                        path = None
                        if dec.args:
                            path = _extract_string(dec.args[0])
                        if path:
                            endpoints.append(
                                {
                                    "method": method,
                                    "path": path,
                                    "file": str(file),
                                    "lineno": node.lineno,
                                }
                            )
    return endpoints


def analyze_health(api_dir: Path, no_import: bool) -> Dict[str, Any]:
    result: Dict[str, Any] = {"keys": []}
    health_func = None
    health_module = api_dir / "app.py"
    if no_import:
        # static scan
        try:
            text = health_module.read_text(encoding="utf-8", errors="ignore").lstrip("\ufeff")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "health":
                    if isinstance(node.body[-1], ast.Return) and isinstance(node.body[-1].value, ast.Dict):
                        keys = []
                        for k in node.body[-1].value.keys:
                            s = _extract_string(k)
                            if s:
                                keys.append(s)
                        result["keys"] = keys
        except Exception:
            pass
        return result
    try:
        sys.path.insert(0, str(api_dir.parent.parent))
        from contract_review_app.api.app import app  # type: ignore
    except Exception:
        return result
    for route in getattr(app, "routes", []):  # type: ignore
        if getattr(route, "path", "") == "/health":
            health_func = route.endpoint
            break
    if health_func is None:
        return result
    try:
        if asyncio.iscoroutinefunction(health_func):
            resp = asyncio.run(health_func())
        else:
            resp = health_func()
        if isinstance(resp, dict):
            result["keys"] = list(resp.keys())
    except Exception:
        pass
    return result


def analyze_backend(root: Path, no_import: bool) -> Dict[str, Any]:
    api_dir = root / "contract_review_app" / "api"
    app_py = api_dir / "app.py"
    cors = analyze_cors(app_py) if app_py.exists() else {}
    endpoints = analyze_endpoints(api_dir)
    health = analyze_health(api_dir, no_import)
    return {"cors": cors, "endpoints": endpoints, "health": health}

# ---------------------------------------------------------------------------
# LLM analysis
# ---------------------------------------------------------------------------

def analyze_env() -> Dict[str, Any]:
    env: Dict[str, Any] = {}
    for k in ENV_PATTERNS:
        env[k] = os.getenv(k)
    for k in list(os.environ.keys()):
        if k.startswith("AZURE_OPENAI_") or k.startswith("MODEL") or k.startswith("LLM_"):
            env[k] = os.getenv(k)
    for secret in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]:
        if secret in env:
            env[secret] = bool(env[secret])
    return env


def analyze_llm(root: Path, endpoints: List[Dict[str, Any]]) -> Dict[str, Any]:
    env = analyze_env()
    api_dir = root / "contract_review_app" / "api"
    files = list(api_dir.glob("*.py"))
    providers: Set[str] = set()
    has_stub = False
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                s = node.value.lower()
                for p in ["openai", "anthropic", "azure", "openrouter"]:
                    if p in s:
                        providers.add(p)
            if isinstance(node, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == "draft_text" for t in node.targets):
                    if isinstance(node.value, ast.Constant) and node.value.value == "":
                        has_stub = True
            if isinstance(node, ast.Return):
                if isinstance(node.value, ast.Constant) and node.value.value == "":
                    has_stub = True
    draft_endpoint = any(ep["path"] == "/api/gpt/draft" for ep in endpoints)
    return {
        "env": env,
        "code": {
            "providers_detected": sorted(providers),
            "has_stub_draft": has_stub,
            "has_draft_endpoint": draft_endpoint,
        },
    }

# ---------------------------------------------------------------------------
# Rule engine analysis
# ---------------------------------------------------------------------------

def analyze_python_rules(root: Path, no_import: bool) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    python: Dict[str, Any] = {"count": 0, "names": []}
    fail: Optional[Dict[str, Any]] = None
    if no_import:
        return python, None
    try:
        import sys
        sys.path.insert(0, str(root))
        from contract_review_app.legal_rules import registry as rules_registry  # type: ignore
        try:
            rules = rules_registry.discover_rules(cache=True)  # type: ignore
        except TypeError:  # older signature
            rules = rules_registry.discover_rules()  # type: ignore
        python["count"] = len(rules)
        python["names"] = [getattr(r, "name", str(r)) for r in rules][:100]
    except Exception as exc:  # pragma: no cover
        fail = {"message": str(exc)}
    return python, fail


def validate_yaml_rule(data: Any) -> bool:
    if not isinstance(data, list):
        return False
    for rule in data:
        if not isinstance(rule, dict):
            return False
        for field in ["id", "title", "severity"]:
            if field not in rule:
                return False
        if not any(k in rule for k in ["patterns", "match", "extract", "advice"]):
            return False
    return True


def analyze_yaml_rules(root: Path) -> Dict[str, Any]:
    packs: List[Dict[str, Any]] = []
    packs_dir = root / "contract_review_app" / "legal_rules" / "policy_packs"
    for f in packs_dir.rglob("*.yml"):
        packs.append(_analyze_yaml_pack(root, f))
    for f in packs_dir.rglob("*.yaml"):
        packs.append(_analyze_yaml_pack(root, f))
    return {"packs": packs}


def _analyze_yaml_pack(root: Path, f: Path) -> Dict[str, Any]:
    info = {"file": rel(f, root), "rules": 0, "valid": False}
    if yaml is None:
        return info
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        info["rules"] = len(data) if isinstance(data, list) else 0
        info["valid"] = validate_yaml_rule(data)
    except Exception:
        pass
    return info


def find_namespace_conflicts(root: Path) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    for f in iter_included_files(root):
        if "tools" in f.parts:
            continue
        if f.suffix != ".py":
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if "legal_rules.rules.registry" in line:
                conflicts.append({"file": rel(f, root), "lineno": i, "line": line.strip()})
    return conflicts


def analyze_rules(root: Path, no_import: bool) -> Dict[str, Any]:
    python_rules, fail = analyze_python_rules(root, no_import)
    yaml_rules = analyze_yaml_rules(root)
    conflicts = find_namespace_conflicts(root)
    result = {"python": python_rules, "yaml": yaml_rules, "namespace_conflicts": conflicts}
    if fail:
        result["python_fail"] = fail
    return result

# ---------------------------------------------------------------------------
# Word Add‑in analysis
# ---------------------------------------------------------------------------

def analyze_manifest(root: Path) -> Dict[str, Any]:
    manifest_path = root / "word_addin_dev" / "manifest.xml"
    info = {"sourceLocation": None, "host": [], "permissions": None}
    if not manifest_path.exists():
        return info
    try:
        tree = ET.parse(manifest_path)
        root_el = tree.getroot()
        ns = {"o": root_el.tag.split("}")[0].strip("{")}
        sl = root_el.find(".//o:DefaultSettings/o:SourceLocation", ns)
        if sl is not None:
            info["sourceLocation"] = sl.get("DefaultValue")
        info["host"] = [h.get("Name") for h in root_el.findall(".//o:Host", ns) if h.get("Name")]
        perm = root_el.find(".//o:Permissions", ns)
        if perm is not None and perm.text:
            info["permissions"] = perm.text.strip()
    except Exception:
        pass
    return info


def analyze_panel(root: Path) -> Dict[str, Any]:
    panel_dir = root / "word_addin_dev"
    files = {
        "taskpane.html": (panel_dir / "taskpane.html").exists(),
        "taskpane.bundle.js": (panel_dir / "taskpane.bundle.js").exists(),
        "panel_selftest.html": (panel_dir / "panel_selftest.html").exists(),
    }
    serve_py = root / "serve_https_panel.py"
    base_url = None
    if serve_py.exists():
        text = serve_py.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"https?://[^'\"\n]+", text)
        if m:
            base_url = m.group(0)
    certs_dir = panel_dir / "certs"
    certs = {
        "localhost.pem": (certs_dir / "localhost.pem").exists(),
        "localhost-key.pem": (certs_dir / "localhost-key.pem").exists(),
    }
    return {"panel_files": files, "base_url": base_url, "certs": certs}

# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def analyze_inventory(root: Path) -> Dict[str, Any]:
    files = iter_included_files(root)
    total = len(files)
    py = sum(1 for f in files if f.suffix == ".py")
    js = sum(1 for f in files if f.suffix in {".js", ".ts", ".tsx"})
    return {
        "counts": {"total_files": total, "py": py, "js": js},
        "ignored": sorted(list(IGNORE_DIRS))
    }

# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def collect_summary(backend: Dict[str, Any], llm: Dict[str, Any], rules: Dict[str, Any], addin: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    expose = set(backend.get("cors", {}).get("expose_headers") or [])
    if not expose or not REQUIRED_EXPOSE_HEADERS.issubset({e.lower() for e in expose}):
        summary.append({
            "severity": "FAIL",
            "area": "backend",
            "message": "CORS expose_headers missing required values",
            "detail": list(expose),
        })
    if addin.get("manifest", {}).get("sourceLocation") in (None, ""):
        summary.append({
            "severity": "FAIL",
            "area": "addin",
            "message": "manifest.xml SourceLocation DefaultValue missing",
            "detail": [],
            "files": ["word_addin_dev/manifest.xml"],
        })
    if rules.get("namespace_conflicts"):
        summary.append({
            "severity": "FAIL",
            "area": "rules",
            "message": "Imports of legal_rules.rules.registry found",
            "detail": rules["namespace_conflicts"],
        })
    if rules.get("python_fail"):
        summary.append({
            "severity": "FAIL",
            "area": "rules",
            "message": "discover_rules() failed",
            "detail": rules.get("python_fail"),
        })
    if llm["code"].get("has_stub_draft"):
        summary.append({
            "severity": "FAIL",
            "area": "llm",
            "message": "Found empty draft text stub",
            "detail": [],
        })
    # WARN conditions
    env = llm.get("env", {})
    draft_ep = llm["code"].get("has_draft_endpoint")
    if draft_ep and not any(env.get(k) for k in env):
        summary.append({
            "severity": "WARN",
            "area": "llm",
            "message": "LLM not configured (rule-only mode)",
            "detail": [],
        })
    panel_files = addin.get("panel", {}).get("panel_files", {})
    if panel_files and not panel_files.get("taskpane.html", False):
        summary.append({
            "severity": "WARN",
            "area": "panel",
            "message": "taskpane.html missing",
            "detail": [],
        })
    if panel_files and not panel_files.get("taskpane.bundle.js", False):
        summary.append({
            "severity": "WARN",
            "area": "panel",
            "message": "taskpane.bundle.js missing",
            "detail": [],
        })
    certs = addin.get("panel", {}).get("certs", {})
    if certs and (not certs.get("localhost.pem") or not certs.get("localhost-key.pem")):
        summary.append({
            "severity": "WARN",
            "area": "panel",
            "message": "Development HTTPS certs missing",
            "detail": [],
        })
    # INFO
    if llm["code"].get("providers_detected"):
        summary.append({
            "severity": "INFO",
            "area": "llm",
            "message": "Providers detected",
            "detail": llm["code"]["providers_detected"],
        })
    if rules.get("python", {}).get("count", 0) > 0:
        summary.append({
            "severity": "INFO",
            "area": "rules",
            "message": f"python rules: {rules['python']['count']}",
            "detail": rules['python']['names'],
        })
    if rules.get("yaml", {}).get("packs"):
        summary.append({
            "severity": "INFO",
            "area": "rules",
            "message": "yaml policy packs analysed",
            "detail": rules['yaml']['packs'],
        })
    return summary


def render_html(data: Dict[str, Any]) -> str:
    ts = _dt.datetime.utcnow().isoformat()
    summary_rows = []
    for item in data["summary"]:
        color = {
            "FAIL": "#dc2626",
            "WARN": "#d97706",
            "INFO": "#2563eb",
        }.get(item["severity"], "#16a34a")
        summary_rows.append(
            f"<tr><td><span style='background:{color};color:white;padding:2px 6px;border-radius:6px'>{item['severity']}</span></td>"
            f"<td>{html.escape(item['area'])}</td><td>{html.escape(item['message'])}</td>"
            f"<td><code>{html.escape(json.dumps(item.get('detail', ''), ensure_ascii=False))}</code></td></tr>"
        )
    summary_html = "".join(summary_rows) or "<tr><td colspan=4>OK</td></tr>"
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>contract_ai analysis</title>
<style>body{{font-family:Arial,Helvetica,sans-serif;padding:24px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px}}</style>
</head><body>
<h1>contract_ai Offline Analysis</h1>
<p>Generated: {ts}</p>
<h2 id='summary'>Summary</h2>
<table><tr><th>Severity</th><th>Area</th><th>Message</th><th>Detail</th></tr>{summary_html}</table>
<h2 id='backend'>Backend</h2><pre>{html.escape(json.dumps(data['backend'], indent=2, ensure_ascii=False))}</pre>
<h2 id='llm'>LLM</h2><pre>{html.escape(json.dumps(data['llm'], indent=2, ensure_ascii=False))}</pre>
<h2 id='rules'>Rules</h2><pre>{html.escape(json.dumps(data['rules'], indent=2, ensure_ascii=False))}</pre>
<h2 id='addin'>Add-in</h2><pre>{html.escape(json.dumps(data['addin'], indent=2, ensure_ascii=False))}</pre>
<h2 id='inventory'>Inventory</h2><pre>{html.escape(json.dumps(data['inventory'], indent=2, ensure_ascii=False))}</pre>
<h2 id='reproduce'>How to reproduce checks</h2><pre>python tools/analyze_project.py --project-root .</pre>
</body></html>"""

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="contract_ai repository analyzer")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-import", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    out_dir = Path(args.out) if args.out else root / "tools" / "reports" / utc_timestamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    backend = analyze_backend(root, args.no_import)
    llm = analyze_llm(root, backend.get("endpoints", []))
    rules = analyze_rules(root, args.no_import)
    manifest = analyze_manifest(root)
    panel = analyze_panel(root)
    addin = {"manifest": manifest, "panel": panel}
    inventory = analyze_inventory(root)
    summary = collect_summary(backend, llm, rules, addin)
    data = {
        "summary": summary,
        "backend": backend,
        "llm": llm,
        "rules": rules,
        "addin": addin,
        "inventory": inventory,
    }
    json_path = out_dir / "analysis.json"
    html_path = out_dir / "analysis.html"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(render_html(data), encoding="utf-8")
    if args.verbose:
        print(f"JSON report: {json_path}\nHTML report: {html_path}")
    has_fail = any(item["severity"] == "FAIL" for item in summary)
    return 2 if has_fail else 0

if __name__ == "__main__":
    raise SystemExit(main())
