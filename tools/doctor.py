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
from datetime import datetime
import time
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

# ---------- transparent state log ----------
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


# ---------- output helpers ----------
def _resolve_out_prefix(out_arg: str) -> Tuple[Path, Path]:
    """
    Backward compatible --out:
    - Directory mode (legacy): if OUT is an existing dir, write <dir>/analysis.json and
      <dir>/analysis.html
    - Prefix mode (new): otherwise (file/prefix), write <prefix>.json and <prefix>.html
    Returns: (out_dir, prefix_without_suffix)
    """
    p = Path(out_arg)

    if p.suffix in {".json", ".html"}:
        prefix = p.with_suffix("")
        out_dir = prefix.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir, prefix

    if p.exists() and p.is_dir():
        out_dir = p
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir, out_dir / "analysis"

    prefix = p.with_suffix("") if p.suffix else p
    out_dir = prefix.parent if str(prefix.parent) != "" else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir, prefix


def render_html_report(data: dict) -> str:
    return (
        "<html><body><pre>"
        + json.dumps(data, indent=2, ensure_ascii=False)
        + "</pre></body></html>"
    )


def _write_reports(out_arg: str, data: dict, write_json: bool, write_html: bool) -> None:
    """Write JSON/HTML and state.log next to them; preserves legacy directory behaviour."""
    out_dir, prefix = _resolve_out_prefix(out_arg)
    out_dir.mkdir(parents=True, exist_ok=True)

    if write_json:
        (prefix.with_suffix(".json")).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    if write_html:
        html = render_html_report(data)
        (prefix.with_suffix(".html")).write_text(html, encoding="utf-8")


# ---------- report ----------
def generate_report(state_log: Path | None = None) -> Dict[str, Any]:
    """If state_log is provided, wrap all gatherers with START/OK/ERR logging."""
    data: Dict[str, Any] = {}
    if state_log is None:
        data["env"] = gather_env()
        data["git"] = gather_git()
        data["precommit"] = gather_precommit()
        backend = gather_backend()
        data["backend"] = backend
        llm = gather_llm(backend)
        data["llm"] = llm

        # --- Backward-compat: duplicate LLM keys into env ---
        for k in ("provider", "model", "timeout_s", "node_is_mock"):
            data["env"][k] = llm.get(k)

        data["service"] = gather_service()
        data["api"] = gather_api()
        data["rules"] = gather_rules()
        data["addin"] = gather_addin()
        data["runtime_checks"] = gather_runtime()
        data["inventory"] = gather_inventory()
        data["repo"] = gather_repo()
        data["quality"] = gather_quality()
        data["smoke"] = gather_smoke()
    else:
        data["env"] = _run_with_state("env", gather_env, state_log)
        data["git"] = _run_with_state("git", gather_git, state_log)
        data["precommit"] = _run_with_state("precommit", gather_precommit, state_log)
        backend = _run_with_state("backend", gather_backend, state_log)
        data["backend"] = backend
        llm = _run_with_state("llm", gather_llm, state_log, backend)
        data["llm"] = llm

        # --- Backward-compat: duplicate LLM keys into env ---
        for k in ("provider", "model", "timeout_s", "node_is_mock"):
            data["env"][k] = llm.get(k)

        data["service"] = _run_with_state("service", gather_service, state_log)
        data["api"] = _run_with_state("api", gather_api, state_log)
        data["rules"] = _run_with_state("rules", gather_rules, state_log)
        data["addin"] = _run_with_state("addin", gather_addin, state_log)
        data["runtime_checks"] = _run_with_state("runtime", gather_runtime, state_log)
        data["inventory"] = _run_with_state("inventory", gather_inventory, state_log)
        data["repo"] = _run_with_state("repo", gather_repo, state_log)
        data["quality"] = _run_with_state("quality", gather_quality, state_log)
        data["smoke"] = _run_with_state("smoke", gather_smoke, state_log)
    return data


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect project diagnostics")
    parser.add_argument(
        "--out",
        required=True,
        help="Output target. Directory (legacy) -> <dir>/analysis.(json|html). Or file prefix -> <prefix>.json/.html.",
    )
    parser.add_argument("--json", action="store_true", help="Write JSON report")
    parser.add_argument("--html", action="store_true", help="Write HTML report")
    args = parser.parse_args(argv)

    out_dir, _prefix = _resolve_out_prefix(args.out)
    state_log = out_dir / "state.log"

    global LOG_ENTRIES
    LOG_ENTRIES = 0

    data = generate_report(state_log)

    try:
        state_path_str = str(state_log.relative_to(ROOT))
    except Exception:
        state_path_str = str(state_log)
    data["state_log"] = {"path": state_path_str, "entries": LOG_ENTRIES}

    data.setdefault(
        "generated_at_utc", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    block_keys = [
        "env",
        "git",
        "precommit",
        "backend",
        "llm",
        "service",
        "api",
        "rules",
        "addin",
        "runtime_checks",
        "inventory",
        "repo",
        "quality",
        "smoke",
    ]
    blocks = [data.get(k, {}) for k in block_keys]
    if len(blocks) != 14:
        blocks = (blocks + [{}] * 14)[:14]
    data["blocks"] = blocks

    _write_reports(
        args.out, data, write_json=bool(args.json), write_html=bool(args.html)
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
