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
        provider = os.getenv("LLM_PROVIDER", "")
        model = os.getenv("LLM_MODEL", "")
        timeout_raw = os.getenv("LLM_TIMEOUT", "")
        try:
            timeout_s = int(timeout_raw) if timeout_raw else 5
        except ValueError:
            timeout_s = 5
        mode_is_mock = (not provider and not model) or provider == "mock" or model == "mock"
        if not provider and not model:
            provider = "mock"
            model = "mock"
            timeout_s = 5
        info.update(
            {
                "provider": provider,
                "model": model,
                "timeout_s": timeout_s,
                "mode_is_mock": mode_is_mock,
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


def generate_report() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    data["env"] = gather_env()
    data["git"] = gather_git()
    backend = gather_backend()
    data["backend"] = backend
    data["llm"] = gather_llm(backend)
    data["service"] = gather_service()
    data["api"] = gather_api()
    data["rules"] = gather_rules()
    data["addin"] = gather_addin()
    data["inventory"] = gather_inventory()
    return data


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect project diagnostics")
    parser.add_argument("--out", required=True, help="Output directory for the report")
    parser.add_argument("--json", action="store_true", help="Write JSON report")
    parser.add_argument("--html", action="store_true", help="Write HTML report")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = generate_report()

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
