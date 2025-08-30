#!/usr/bin/env python3
"""Collect a diagnostic snapshot of the project environment."""

from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
import time
import re
from pathlib import Path
from typing import Any, Dict, List
import html

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ENV_VARS = [
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_TIMEOUT",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "AI_PROVIDER",
]
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}

BLOCKS = [
    {"id": "B0", "name": "Project Doctor & Quality"},
    {"id": "B1", "name": "SSOT Schemas"},
    {"id": "B2", "name": "Document Intake & Parsing"},
    {"id": "B3", "name": "Rule Engine v2"},
    {"id": "B4", "name": "LLM Orchestrator/Proxy"},
    {"id": "B5", "name": "Legal Corpus & Metadata"},
    {"id": "B6", "name": "Hybrid Retrieval"},
    {"id": "B7", "name": "Citation Resolver API"},
    {"id": "B8", "name": "API Layer Harmonization"},
    {"id": "B9", "name": "Word Add-in UX"},
    {"id": "B10", "name": "Learning & Feedback"},
    {"id": "B11", "name": "Compliance & Security"},
    {"id": "B12", "name": "Monitoring/CI/CD"},
    {"id": "B13", "name": "Deployment & Runbooks"},
]

# ---------- transparent state log ----------
LOG_ENTRIES = 0


def _log_state(path: Path, message: str) -> None:
    """Append a timestamped message to the state log."""
    global LOG_ENTRIES
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")
    LOG_ENTRIES += 1


def _run_with_state(name: str, func, path: Path, *args, **kwargs):
    """Run *func* logging START/OK/ERR states."""
    _log_state(path, f"START {name}")
    try:
        result = func(*args, **kwargs)
        extra = ""
        if name == "llm":
            provider = os.getenv("LLM_PROVIDER") or "unknown"
            model = os.getenv("LLM_MODEL") or "unknown"
            extra = f" provider={provider} model={model}"
        _log_state(path, f"OK {name}{extra}")
        return result
    except Exception as exc:  # pragma: no cover
        _log_state(path, f"ERR {name} error={exc}")
        return {"error": traceback.format_exc()}


# ---------- helpers & gatherers ----------
def _run_cmd(cmd: List[str]) -> str:
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=str(ROOT)
        )
        return res.stdout.strip()
    except Exception:
        return traceback.format_exc()


def gather_env() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "python": sys.version,
        "env": {k: os.getenv(k) for k in ENV_VARS},
        "pythonpath": os.getenv("PYTHONPATH", ""),
    }
    try:
        info["pip_freeze"] = _run_cmd(
            [sys.executable, "-m", "pip", "freeze"]
        ).splitlines()
    except Exception:
        info["pip_freeze_error"] = traceback.format_exc()
    return info


def gather_git() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        info["branch"] = _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        info["head"] = _run_cmd(["git", "rev-parse", "HEAD"])
        info["status"] = _run_cmd(["git", "status", "-sb"])
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_precommit() -> Dict[str, Any]:
    info: Dict[str, Any] = {"config_exists": False, "hooks": []}
    try:
        cfg = ROOT / ".pre-commit-config.yaml"
        if cfg.exists():
            info["config_exists"] = True
            import yaml  # type: ignore

            data = yaml.safe_load(cfg.read_text()) or {}
            hooks: List[str] = []
            for repo in data.get("repos", []):
                for hook in repo.get("hooks", []):
                    hook_id = hook.get("id")
                    if hook_id:
                        hooks.append(hook_id)
            info["hooks"] = hooks
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_backend() -> Dict[str, Any]:
    info: Dict[str, Any] = {"endpoints": []}
    try:
        from contract_review_app.api.app import app  # type: ignore

        for route in getattr(app, "routes", []):
            methods = getattr(route, "methods", set())
            path = getattr(route, "path", "")
            endpoint = getattr(route, "endpoint", None)
            if not methods or not path or endpoint is None:
                continue
            file = None
            lineno = None
            try:
                file = inspect.getsourcefile(endpoint)
                _, lineno = inspect.getsourcelines(endpoint)
            except Exception:
                pass
            for m in methods:
                info["endpoints"].append(
                    {"method": m, "path": path, "file": file, "lineno": lineno}
                )
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_llm(backend: Dict[str, Any]) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        provider = os.getenv("LLM_PROVIDER", "")
        model = os.getenv("LLM_MODEL", "")
        timeout_raw = os.getenv("LLM_TIMEOUT", "")
        try:
            timeout_s = int(timeout_raw) if timeout_raw else 5
        except ValueError:
            timeout_s = 5

        mode_is_mock = (
            (not provider and not model) or provider == "mock" or model == "mock"
        )
        if not provider and not model:
            provider, model, timeout_s = "mock", "mock", 5

        info.update(
            {
                "provider": provider,
                "model": model,
                "timeout_s": timeout_s,
                "node_is_mock": mode_is_mock,
            }
        )

        clients_dir = ROOT / "contract_review_app" / "gpt" / "clients"
        providers: List[str] = []
        if clients_dir.exists():
            for p in clients_dir.glob("*_client.py"):
                providers.append(p.stem.replace("_client", ""))
        info["providers_detected"] = sorted(providers)

        info["has_draft_endpoint"] = any(
            e.get("path", "").endswith("draft") and e.get("method") == "POST"
            for e in backend.get("endpoints", [])
        )
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_service() -> Dict[str, Any]:
    info: Dict[str, Any] = {"exports": {}}
    try:
        import contract_review_app.gpt.service as svc  # type: ignore

        names = [
            "LLMService",
            "load_llm_config",
            "ProviderTimeoutError",
            "ProviderConfigError",
        ]
        info["exports"] = {name: hasattr(svc, name) for name in names}
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_api() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        import contract_review_app.api.app as app_mod  # type: ignore

        info["has__analyze_document"] = hasattr(app_mod, "_analyze_document")
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_rules() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "python": {"count": 0, "samples": []},
        "yaml": {"count": 0, "samples": []},
    }
    try:
        from contract_review_app.legal_rules.rules import registry  # type: ignore

        keys = sorted(registry.keys())
        info["python"] = {"count": len(keys), "samples": keys[:8]}

        yaml_dir = ROOT / "contract_review_app" / "legal_rules" / "policy_packs"
        if yaml_dir.exists():
            yaml_files = [
                p.relative_to(yaml_dir).as_posix() for p in yaml_dir.rglob("*.yml")
            ] + [p.relative_to(yaml_dir).as_posix() for p in yaml_dir.rglob("*.yaml")]
            yaml_files = sorted(set(yaml_files))
            info["yaml"] = {"count": len(yaml_files), "samples": yaml_files[:8]}
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_addin() -> Dict[str, Any]:
    info: Dict[str, Any] = {"manifest": {"exists": False}, "bundle": {"exists": False}}
    try:
        manifest_path = ROOT / "word_addin_dev" / "manifest.xml"
        manifest_info: Dict[str, Any] = {"exists": False}
        if manifest_path.exists():
            manifest_info["exists"] = True
            try:
                import xml.etree.ElementTree as ET

                tree = ET.parse(manifest_path)
                root = tree.getroot()
                ns = {"n": root.tag.split("}")[0].strip("{")}
                manifest_info["id"] = root.findtext("n:Id", default="", namespaces=ns)
                manifest_info["version"] = root.findtext(
                    "n:Version", default="", namespaces=ns
                )
                source = root.find("n:DefaultSettings/n:SourceLocation", namespaces=ns)
                if source is not None:
                    manifest_info["source"] = source.get("DefaultValue")
                permissions = root.findtext("n:Permissions", default="", namespaces=ns)
                if permissions:
                    manifest_info["permissions"] = permissions
            except Exception:
                manifest_info["error"] = traceback.format_exc()
        info["manifest"] = manifest_info

        bundle_info: Dict[str, Any] = {"exists": False}
        app_dir = ROOT / "word_addin_dev" / "app"
        if app_dir.exists():
            bundle_candidates = list(app_dir.glob("build-*/taskpane.bundle.js"))
            if bundle_candidates:
                latest = max(bundle_candidates, key=lambda p: p.stat().st_mtime)
                st = latest.stat()
                from datetime import datetime, timezone

                bundle_info = {
                    "exists": True,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
        info["bundle"] = bundle_info
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def _probe_runtime(client: Any, path: str) -> Dict[str, Any]:
    start = time.perf_counter()
    resp = client.get(path)
    ms = (time.perf_counter() - start) * 1000.0
    return {"status": resp.status_code, "latency_ms": int(ms)}


def gather_runtime() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        from contract_review_app.api.app import app  # type: ignore
        from starlette.testclient import TestClient

        client = TestClient(app)
        for name, path in [("health", "/health"), ("openapi", "/openapi.json")]:
            try:
                info[name] = _probe_runtime(client, path)
            except Exception:
                info[name] = {"status": None, "error": traceback.format_exc()}
    except Exception:
        err = traceback.format_exc()
        info["health"] = {"status": None, "error": err}
        info["openapi"] = {"status": None, "error": err}
    return info


def _has_mypy_config(root: Path) -> bool:
    cfgs = ["mypy.ini", ".mypy.ini", "setup.cfg", "pyproject.toml"]
    for name in cfgs:
        p = root / name
        if not p.exists():
            continue
        if name == "setup.cfg":
            try:
                if "[mypy" in p.read_text(encoding="utf-8"):
                    return True
            except Exception:
                continue
        elif name == "pyproject.toml":
            try:
                if "[tool.mypy]" in p.read_text(encoding="utf-8"):
                    return True
            except Exception:
                continue
        else:
            return True
    return False


def gather_quality() -> Dict[str, Any]:
    info: Dict[str, Any] = {"ruff": {}, "mypy": {}}
    # --- Ruff: cross-version counting via --statistics ---
    try:
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                ".",
                "--quiet",
                "--exit-zero",
                "--statistics",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        total = 0
        for line in (res.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\s*(\d+)\b", line)
            if m:
                total += int(m.group(1))
        info["ruff"] = {"status": "ok", "issues_total": total}
    except Exception:
        info["ruff"] = {
            "status": "error",
            "issues_total": None,
            "error": traceback.format_exc(),
        }

    # --- mypy: only if config exists ---
    if _has_mypy_config(ROOT):
        try:
            res = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    "contract_review_app",
                    "--hide-error-context",
                    "--no-error-summary",
                ],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                check=False,
            )
            out = res.stdout + "\n" + res.stderr
            m = re.search(r"Found\s+(\d+)\s+error", out)
            total = int(m.group(1)) if m else 0
            status = "ok" if res.returncode in (0, 1) else "error"
            info["mypy"] = {"status": status, "errors_total": total}
        except Exception:
            info["mypy"] = {
                "status": "error",
                "errors_total": None,
                "error": traceback.format_exc(),
            }
    else:
        info["mypy"] = {"status": "skipped", "errors_total": 0}

    return info


def gather_smoke() -> Dict[str, Any]:
    """Optionally run a small pytest subset and record a summary.

    Enabled by default, unless DOCTOR_SMOKE == "0".
    Recursion guard: DOCTOR_SMOKE_ACTIVE == "1".
    """
    info: Dict[str, Any] = {"enabled": False, "passed": 0, "failed": 0, "skipped": 0}

    if os.getenv("DOCTOR_SMOKE_ACTIVE") == "1":
        return info

    if os.getenv("DOCTOR_SMOKE", "1") == "0":
        return info

    info["enabled"] = True
    try:
        env = os.environ.copy()
        env["DOCTOR_SMOKE_ACTIVE"] = "1"
        env.pop("DOCTOR_SMOKE", None)

        cmd = [sys.executable, "-m", "pytest", "-q", "tests/codex"]
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=False, cwd=str(ROOT), env=env
        )
        clean = re.sub(
            r"\x1b\[[0-9;]*m", "", (res.stdout or "") + "\n" + (res.stderr or "")
        )

        mp = re.search(r"(\d+)\s+passed", clean)
        mf = re.search(r"(\d+)\s+failed", clean)
        ms = re.search(r"(\d+)\s+skipped", clean)
        if mp:
            info["passed"] = int(mp.group(1))
        if mf:
            info["failed"] = int(mf.group(1))
        if ms:
            info["skipped"] = int(ms.group(1))

        # fallback: progress line like ".F.s["
        if not (mp or mf or ms):
            prog = re.search(r"([\.FEsx]+)\s*\[", clean or "")
            if prog:
                p = prog.group(1)
                info["passed"] = p.count(".")
                info["failed"] = p.count("F") + p.count("E")
                info["skipped"] = p.count("s")
    except Exception:
        info["error"] = traceback.format_exc()

    return info


def gather_inventory() -> Dict[str, Any]:
    counts = {"py": 0, "js": 0}
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            if f.endswith(".py"):
                counts["py"] += 1
            elif f.endswith(".js"):
                counts["js"] += 1
    return {"files": counts, "ignored_dirs": sorted(IGNORED_DIRS)}


def gather_repo() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        files = _run_cmd(["git", "ls-files"]).splitlines()
        tracked_pyc = [f for f in files if f.endswith(".pyc")]
        info["tracked_pyc"] = len(tracked_pyc)
        info["suggestions"] = [
            "Add __pycache__/ and *.pyc to .gitignore",
            "To purge cached: git rm -r --cached **/__pycache__ *.pyc && git commit -m 'purge pyc'",
        ]
    except Exception:
        info["error"] = traceback.format_exc()
    return info


# ---------- maturity matrix assessors ----------

def _status_score(status: str, adjustment: int = 0) -> int:
    base = {"OK": 100, "WARN": 60, "MISSING": 0}.get(status, 0)
    adj = max(-20, min(20, adjustment))
    return max(0, min(100, base + adj))


def assess_B0(data: Dict[str, Any]) -> Dict[str, Any]:
    quality = data.get("quality", {}).get("ruff", {})
    ruff_total = quality.get("issues_total")
    ruff_ok = quality.get("status") == "ok" and ruff_total is not None
    try:  # pytest discoverable
        import pytest  # noqa: F401

        pytest_ok = True
    except Exception:  # pragma: no cover - pytest missing
        pytest_ok = False
    precommit_exists = data.get("precommit", {}).get("config_exists", False)
    status = "OK" if ruff_ok and pytest_ok else ("WARN" if ruff_ok or pytest_ok else "MISSING")
    metrics = {
        "ruff_issues": ruff_total,
        "pytest": pytest_ok,
        "precommit": bool(precommit_exists),
    }
    score = _status_score(status, adjustment=-min(20, int(ruff_total or 0)))
    return {"status": status, "score": score, "metrics": metrics, "notes": []}


def assess_B1(data: Dict[str, Any]) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    notes: List[str] = []
    try:
        import contract_review_app.core.schemas as schemas  # type: ignore

        found = {name: hasattr(schemas, name) for name in ["Finding", "Citation", "Evidence", "ParsedDocument"]}
        metrics.update(found)
        status = "OK"
        if not (found.get("Citation") and found.get("Evidence")):
            status = "WARN"
    except Exception:
        status = "MISSING"
        notes.append("core/schemas.py not found")
    score = _status_score(status)
    return {"status": status, "score": score, "metrics": metrics, "notes": notes}


def assess_B2(data: Dict[str, Any]) -> Dict[str, Any]:
    modules: List[str] = []
    for rel in [
        "contract_review_app/document/normalize.py",
        "contract_review_app/document/load_docx_text.py",
        "contract_review_app/core/load_docx_text.py",
    ]:
        p = ROOT / rel
        if p.exists():
            txt = ""
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:  # pragma: no cover - encoding issues
                pass
            if "def normalize" in txt or "def load" in txt:
                modules.append(rel)
    status = "OK" if modules else "MISSING"
    metrics = {"modules": modules}
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_B3(data: Dict[str, Any]) -> Dict[str, Any]:
    rules = data.get("rules", {})
    py_count = int(rules.get("python", {}).get("count", 0))
    yaml_count = int(rules.get("yaml", {}).get("count", 0))
    total = py_count + yaml_count
    status = "MISSING"
    if total > 0:
        status = "OK" if py_count >= 5 or yaml_count >= 1 else "WARN"
    metrics = {"rules_python": py_count, "rules_yaml": yaml_count}
    adjustment = min(20, py_count) if status == "OK" else 0
    score = _status_score(status, adjustment=adjustment)
    notes: List[str] = []
    return {"status": status, "score": score, "metrics": metrics, "notes": notes}


def assess_B4(data: Dict[str, Any]) -> Dict[str, Any]:
    llm = data.get("llm", {})
    service = data.get("service", {})
    providers = llm.get("providers_detected", []) or []
    has_service = bool(service.get("exports", {}).get("LLMService"))
    draft_endpoint = bool(llm.get("has_draft_endpoint"))
    status = "MISSING"
    if has_service or providers:
        status = "WARN"
    if has_service and providers:
        status = "OK" if not llm.get("node_is_mock") else "WARN"
    metrics = {
        "providers": providers,
        "service_exports": has_service,
        "draft_endpoint": draft_endpoint,
    }
    adjustment = min(20, len(providers) * 5) if status == "OK" else 0
    score = _status_score(status, adjustment=adjustment)
    notes: List[str] = []
    return {"status": status, "score": score, "metrics": metrics, "notes": notes}


def assess_B5(data: Dict[str, Any]) -> Dict[str, Any]:
    notes: List[str] = []
    corpus_dir = ROOT / "contract_review_app" / "corpus"
    db_models = ROOT / "contract_review_app" / "db" / "models.py"
    present = corpus_dir.exists() or db_models.exists()
    status = "OK" if present else "MISSING"
    if not present:
        notes.append("corpus not initialized")
    metrics = {"corpus_dir": corpus_dir.exists(), "db_models": db_models.exists()}
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": notes}


def assess_B6(data: Dict[str, Any]) -> Dict[str, Any]:
    search_dir = ROOT / "contract_review_app" / "search"
    modules: List[str] = []
    funcs_found = 0
    if search_dir.exists():
        for p in search_dir.rglob("*.py"):
            name = p.stem
            if any(key in name for key in ["qdrant", "faiss", "elastic", "search", "vector"]):
                txt = p.read_text(encoding="utf-8", errors="ignore")
                modules.append(p.relative_to(ROOT).as_posix())
                if "hybrid_search" in txt or "def search" in txt:
                    funcs_found += 1
    status = "OK" if funcs_found else ("WARN" if modules else "MISSING")
    metrics = {"modules": modules, "search_funcs": funcs_found}
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_B7(data: Dict[str, Any]) -> Dict[str, Any]:
    resolver_path = ROOT / "contract_review_app" / "core" / "citation_resolver.py"
    has_resolver = resolver_path.exists()
    has_func = False
    if has_resolver:
        txt = resolver_path.read_text(encoding="utf-8", errors="ignore")
        has_func = "def resolve" in txt
    metrics = {"resolver": has_resolver, "resolve_funcs": int(has_func)}
    status = "OK" if has_resolver and has_func else "MISSING"
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_B8(data: Dict[str, Any]) -> Dict[str, Any]:
    endpoints = data.get("backend", {}).get("endpoints", [])
    wanted = [
        "/api/analyze",
        "/api/gpt/draft",
        "/api/suggest_edits",
        "/api/qa-recheck",
    ]
    learning_prefix = "/api/learning"
    present = []
    for ep in endpoints:
        path = ep.get("path", "")
        if path in wanted or path.startswith(learning_prefix):
            present.append(path)
    status = "MISSING"
    if present:
        status = "OK" if len(present) >= 3 else "WARN"
    metrics = {"present": sorted(set(present))}
    adjustment = min(20, len(present)) if status == "OK" else 0
    score = _status_score(status, adjustment=adjustment)
    return {"status": status, "score": score, "metrics": metrics, "notes": []}


def assess_B9(data: Dict[str, Any]) -> Dict[str, Any]:
    addin = data.get("addin", {})
    manifest = addin.get("manifest", {}).get("exists", False)
    bundle = addin.get("bundle", {}).get("exists", False)
    status = "MISSING"
    if manifest and bundle:
        status = "OK"
    elif manifest or bundle:
        status = "WARN"
    metrics = {"manifest": manifest, "bundle": bundle}
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_B10(data: Dict[str, Any]) -> Dict[str, Any]:
    endpoints = data.get("backend", {}).get("endpoints", [])
    learning_eps = [ep for ep in endpoints if str(ep.get("path", "")).startswith("/api/learning")]
    models_dir = ROOT / "contract_review_app" / "learning"
    has_models = models_dir.exists()
    status = "OK" if learning_eps and has_models else ("WARN" if learning_eps else "MISSING")
    metrics = {"endpoints": [ep.get("path") for ep in learning_eps], "models": has_models}
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_B11(data: Dict[str, Any]) -> Dict[str, Any]:
    env = data.get("env", {}).get("env", {})
    flags = [k for k, v in env.items() if k and ("RETENTION" in k.upper() or "PERMISSION" in k.upper())]
    status = "OK" if flags else "WARN"
    metrics = {"security_flags": flags}
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_B12(data: Dict[str, Any]) -> Dict[str, Any]:
    workflows = list((ROOT / ".github" / "workflows").glob("*.yml"))
    ruff_ok = data.get("quality", {}).get("ruff", {}).get("status") == "ok"
    status = "OK" if workflows and ruff_ok else "WARN"
    metrics = {"workflows": len(workflows), "ruff_ok": ruff_ok}
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_B13(data: Dict[str, Any]) -> Dict[str, Any]:
    dockerfile = ROOT / "Dockerfile"
    compose = ROOT / "docker-compose.yml"
    compose2 = ROOT / "docker-compose.yaml"
    helm = ROOT / "helm"
    present = dockerfile.exists() or compose.exists() or compose2.exists() or helm.exists()
    status = "OK" if present else "MISSING"
    metrics = {
        "dockerfile": dockerfile.exists(),
        "docker_compose": compose.exists() or compose2.exists(),
        "helm": helm.exists(),
    }
    return {"status": status, "score": _status_score(status), "metrics": metrics, "notes": []}


def assess_blocks(data: Dict[str, Any]) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    total = 0
    for block in BLOCKS:
        func = globals().get(f"assess_{block['id']}")
        if not callable(func):
            continue
        res = func(data)
        res.update(block)
        results.append(res)
        total += res.get("score", 0)
    overall = int(round(total / len(results))) if results else 0
    return {"blocks": results, "overall_score": overall}


# ---------- report ----------
def generate_report(state_log: Path | None = None) -> Dict[str, Any]:
    """Collect raw data and assess maturity blocks."""
    gathered: Dict[str, Any] = {}
    if state_log is None:
        gathered["env"] = gather_env()
        gathered["git"] = gather_git()
        gathered["precommit"] = gather_precommit()
        backend = gather_backend()
        gathered["backend"] = backend
        llm = gather_llm(backend)
        gathered["llm"] = llm

        for k in ("provider", "model", "timeout_s", "node_is_mock"):
            gathered["env"][k] = llm.get(k)

        gathered["service"] = gather_service()
        gathered["api"] = gather_api()
        gathered["rules"] = gather_rules()
        gathered["addin"] = gather_addin()
        gathered["runtime_checks"] = gather_runtime()
        gathered["inventory"] = gather_inventory()
        gathered["repo"] = gather_repo()
        gathered["quality"] = gather_quality()
        gathered["smoke"] = gather_smoke()
    else:
        gathered["env"] = _run_with_state("env", gather_env, state_log)
        gathered["git"] = _run_with_state("git", gather_git, state_log)
        gathered["precommit"] = _run_with_state("precommit", gather_precommit, state_log)
        backend = _run_with_state("backend", gather_backend, state_log)
        gathered["backend"] = backend
        llm = _run_with_state("llm", gather_llm, state_log, backend)
        gathered["llm"] = llm

        for k in ("provider", "model", "timeout_s", "node_is_mock"):
            gathered["env"][k] = llm.get(k)

        gathered["service"] = _run_with_state("service", gather_service, state_log)
        gathered["api"] = _run_with_state("api", gather_api, state_log)
        gathered["rules"] = _run_with_state("rules", gather_rules, state_log)
        gathered["addin"] = _run_with_state("addin", gather_addin, state_log)
        gathered["runtime_checks"] = _run_with_state("runtime", gather_runtime, state_log)
        gathered["inventory"] = _run_with_state("inventory", gather_inventory, state_log)
        gathered["repo"] = _run_with_state("repo", gather_repo, state_log)
        gathered["quality"] = _run_with_state("quality", gather_quality, state_log)
        gathered["smoke"] = _run_with_state("smoke", gather_smoke, state_log)

    assessment = assess_blocks(gathered)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data: Dict[str, Any] = {
        "generated_at_utc": timestamp,
        "overall_score": assessment["overall_score"],
        "blocks": assessment["blocks"],
    }
    data.update(gathered)
    return data


def render_html_report(data: Dict[str, Any]) -> str:
    blocks = data.get("blocks", [])
    style = (
        "<style>body{font-family:sans-serif;}table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ccc;padding:4px;}"
        ".OK{background:#c8e6c9;} .WARN{background:#fff9c4;} .MISSING{background:#ffcdd2;}"
        "details{margin-top:1em;}" "</style>"
    )
    rows = []
    for b in blocks:
        metrics = ", ".join(f"{k}={v}" for k, v in b.get("metrics", {}).items())
        rows.append(
            f"<tr><td><a href='#{b['id']}'>{b['id']}</a></td><td>{b['name']}</td>"
            f"<td class='{b['status']}'><span>{b['status']}</span></td><td>{b['score']}</td><td>{metrics}</td></tr>"
        )
    table = (
        "<table><tr><th>ID</th><th>Name</th><th>Status</th><th>Score</th><th>Metrics</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    details = "".join(
        f"<details id='{b['id']}'><summary>{b['id']} - {b['name']}</summary><pre>"
        + html.escape(json.dumps(b, indent=2, ensure_ascii=False))
        + "</pre></details>"
        for b in blocks
    )
    body = (
        f"<h1>Doctor Report</h1><p>Generated at {data.get('generated_at_utc')} "
        f"Overall score: {data.get('overall_score')}</p>" + table + details
    )
    return f"<html><head><meta charset='utf-8'><title>Doctor Report</title>{style}</head><body>{body}</body></html>"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect project diagnostics")
    parser.add_argument("--out", required=True, help="Output file prefix for the report")
    parser.add_argument("--json", action="store_true", help="Write JSON report")
    parser.add_argument("--html", action="store_true", help="Write HTML report")
    args = parser.parse_args(argv)

    prefix = Path(args.out)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    state_log = prefix.parent / "state.log"

    global LOG_ENTRIES
    LOG_ENTRIES = 0

    data = generate_report(state_log)

    try:
        state_path_str = str(state_log.relative_to(ROOT))
    except Exception:
        state_path_str = str(state_log)
    data["state_log"] = {"path": state_path_str, "entries": LOG_ENTRIES}

    if not args.json and not args.html:
        args.json = True
        args.html = True
    if args.json:
        prefix.with_suffix(".json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if args.html:
        prefix.with_suffix(".html").write_text(
            render_html_report(data), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
