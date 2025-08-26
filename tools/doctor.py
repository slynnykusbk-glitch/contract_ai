#!/usr/bin/env python3
"""Project diagnostics helper.

Collects environment and application information and writes a JSON/HTML
report. The script is intentionally defensive: any import errors are captured
and recorded in the output so the script itself exits successfully.
"""
from __future__ import annotations

#!/usr/bin/env python3
"""Collect a diagnostic snapshot of the project environment."""

import argparse
import inspect
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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


LOG_ENTRIES = 0


def _log_state(path: Path, message: str) -> None:
    """Append a timestamped message to the state log."""
    global LOG_ENTRIES
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
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
    except Exception as exc:  # pragma: no cover - unexpected
        _log_state(path, f"ERR {name} error={exc}")
        return {"error": traceback.format_exc()}


def _run_cmd(cmd: List[str]) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
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
        info["pip_freeze"] = _run_cmd([sys.executable, "-m", "pip", "freeze"]).splitlines()
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
                info["endpoints"].append({
                    "method": m,
                    "path": path,
                    "file": file,
                    "lineno": lineno,
                })
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_llm(backend: Dict[str, Any]) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
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


def gather_rules() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "python": {"count": 0, "names": []},
        "aliases_present": {},
    }
    try:
        rules_dir = ROOT / "contract_review_app" / "legal_rules" / "rules"
        names = [p.stem for p in rules_dir.glob("*.py") if p.name != "__init__.py"]
        info["python"] = {"count": len(names), "names": sorted(names)}
        from contract_review_app.legal_rules import registry as rules_registry  # type: ignore

        aliases_to_check = [
            "dispute_resolution",
            "indemnification",
            "nda",
            "force_majeur",
            "ogma",
        ]
        for alias in aliases_to_check:
            try:
                info["aliases_present"][alias] = rules_registry.normalize_clause_type(alias)
            except Exception:
                info["aliases_present"][alias] = None
        yaml_dir = ROOT / "contract_review_app" / "legal_rules" / "policy_packs"
        yaml_files = list(yaml_dir.glob("**/*.yml")) + list(yaml_dir.glob("**/*.yaml"))
        if yaml_files:
            info["yaml"] = [str(p.relative_to(ROOT)) for p in yaml_files]
    except Exception:
        info["error"] = traceback.format_exc()
    return info


def gather_addin() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    try:
        addin_dir = ROOT / "word_addin_dev"
        if addin_dir.exists():
            manifest = next(addin_dir.glob("**/manifest*.xml"), None)
            taskpane = next(addin_dir.glob("**/taskpane*.*"), None)
            cert = next(addin_dir.glob("**/*.pem"), None)
            info["manifest"] = str(manifest.relative_to(ROOT)) if manifest else None
            info["taskpane"] = str(taskpane.relative_to(ROOT)) if taskpane else None
            info["cert"] = str(cert.relative_to(ROOT)) if cert else None
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


def generate_report(state_log: Path | None = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if state_log is None:
        data["env"] = gather_env()
        data["git"] = gather_git()
        backend = gather_backend()
        data["backend"] = backend
        data["llm"] = gather_llm(backend)
        data["rules"] = gather_rules()
        data["addin"] = gather_addin()
        data["inventory"] = gather_inventory()
    else:
        data["env"] = _run_with_state("env", gather_env, state_log)
        data["git"] = _run_with_state("git", gather_git, state_log)
        backend = _run_with_state("backend", gather_backend, state_log)
        data["backend"] = backend
        data["llm"] = _run_with_state("llm", gather_llm, state_log, backend)
        data["rules"] = _run_with_state("rules", gather_rules, state_log)
        data["addin"] = _run_with_state("addin", gather_addin, state_log)
        data["inventory"] = _run_with_state("inventory", gather_inventory, state_log)
    return data


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect project diagnostics")
    parser.add_argument("--out", required=True, help="Output directory for the report")
    parser.add_argument("--json", action="store_true", help="Write JSON report")
    parser.add_argument("--html", action="store_true", help="Write HTML report")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    state_log = out_dir / "state.log"

    global LOG_ENTRIES
    LOG_ENTRIES = 0

    data = generate_report(state_log)

    try:
        state_path_str = str(state_log.relative_to(ROOT))
    except Exception:
        state_path_str = str(state_log)
    data["state_log"] = {"path": state_path_str, "entries": LOG_ENTRIES}

    if args.json:
        (out_dir / "analysis.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if args.html:
        html = "<html><body><pre>" + json.dumps(data, indent=2, ensure_ascii=False) + "</pre></body></html>"
        (out_dir / "analysis.html").write_text(html, encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
