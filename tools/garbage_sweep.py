#!/usr/bin/env python3
"""Run heuristics to identify unused or fragile artifacts.

This utility orchestrates TypeScript, Python, asset, workflow, and file-size
checks and emits both Markdown and JSON reports under ``reports/``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # Python 3.11+
    from importlib import metadata as importlib_metadata
except ImportError:  # pragma: no cover - fallback for older Pythons
    import importlib_metadata  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO_ROOT / "reports"
REPORT_MD = REPORT_DIR / "garbage_report.md"
REPORT_JSON = REPORT_DIR / "garbage_report.json"
TS_PROJECT = REPO_ROOT / "word_addin_dev"
TS_TSCONFIG = TS_PROJECT / "tsconfig.json"
TS_APP_DIR = TS_PROJECT / "app"

SECTION_ORDER = [
    "unused_exports",
    "unused_dependencies",
    "orphan_tests_and_snapshots",
    "orphan_assets",
    "workflows",
    "big_files",
    "fragile_tests",
]

ENTRY_FIELDS = ["path", "type", "reason", "evidence", "suggested_action", "confidence"]


@dataclass
class ReportEntry:
    path: str
    type: str
    reason: str
    evidence: str
    suggested_action: str
    confidence: str
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_row(self) -> List[str]:
        return [self.path, self.type, self.reason, self.evidence, self.suggested_action, self.confidence]

    def to_dict(self) -> Dict[str, object]:
        payload = {field: getattr(self, field) for field in ENTRY_FIELDS}
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class Section:
    title: str
    entries: List[ReportEntry] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "title": self.title,
            "entries": [entry.to_dict() for entry in self.entries],
            "notes": self.notes,
        }


def run_command(cmd: Sequence[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """Run a subprocess command and capture stdout/stderr."""
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def ensure_reports_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def add_section(sections: Dict[str, Section], key: str, title: str) -> Section:
    if key not in sections:
        sections[key] = Section(title=title)
    return sections[key]


def gather_ts_unused_exports(section: Section) -> None:
    if not TS_TSCONFIG.exists():
        section.notes.append("tsconfig.json not found; skipped ts-prune run.")
        return

    project_flag = os.path.relpath(TS_TSCONFIG, REPO_ROOT)
    cmd = [
        "npx",
        "--yes",
        "ts-prune",
        "-p",
        project_flag,
        "--skip-dts",
    ]
    rc, stdout, stderr = run_command(cmd, cwd=REPO_ROOT)
    if rc not in (0, 1):  # ts-prune exits with 1 when findings are present
        section.notes.append(
            f"ts-prune failed (exit {rc}): {stderr.strip() or stdout.strip() or 'no output'}"
        )
        return

    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in lines:
        if " - " not in line:
            continue
        lhs, rhs = line.split(" - ", 1)
        file_part = lhs.split(":", 1)[0]
        if not file_part.startswith("word_addin_dev/app/"):
            # Skip config and tooling exports outside the add-in app tree.
            continue
        confidence = "High"
        if "used in module" in rhs:
            confidence = "Medium"
        entry = ReportEntry(
            path=file_part,
            type="ts-export",
            reason=f"Export '{rhs.split()[0]}' has no external imports (ts-prune).",
            evidence=line,
            suggested_action="Confirm the export is needed; otherwise move it to local scope or archive it.",
            confidence=confidence,
            metadata={"symbol": rhs.split(" ", 1)[0], "raw": line},
        )
        section.entries.append(entry)

    if not lines:
        section.notes.append("ts-prune reported no unused exports.")


def gather_ts_depcheck(section: Section) -> None:
    if not TS_PROJECT.exists():
        section.notes.append("word_addin_dev directory missing; depcheck skipped.")
        return
    cmd = ["npx", "--yes", "depcheck", "--json"]
    rc, stdout, stderr = run_command(cmd, cwd=TS_PROJECT)
    if not stdout.strip():
        section.notes.append(f"depcheck failed (exit {rc}): {stderr.strip() or 'no output'}")
        return
    if rc not in (0, 1):
        section.notes.append(f"depcheck exited with {rc}, continuing with parsed stdout")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - unexpected formatting
        section.notes.append(f"depcheck JSON parse error: {exc}")
        return

    unused_deps = payload.get("dependencies", []) or []
    unused_devdeps = payload.get("devDependencies", []) or []
    missing = payload.get("missing", {}) or {}

    for dep in unused_deps:
        section.entries.append(
            ReportEntry(
                path="word_addin_dev/package.json",
                type="npm-dependency",
                reason=f"Dependency '{dep}' is not used in source files (depcheck).",
                evidence=f"depcheck unused dependencies: {dep}",
                suggested_action="Verify and remove from package.json if truly unused.",
                confidence="High",
            )
        )
    for dep in unused_devdeps:
        section.entries.append(
            ReportEntry(
                path="word_addin_dev/package.json",
                type="npm-devDependency",
                reason=f"Dev dependency '{dep}' is not referenced by code or scripts (depcheck).",
                evidence=f"depcheck unused devDependencies: {dep}",
                suggested_action="Drop from devDependencies or add the missing usage.",
                confidence="High",
            )
        )
    for pkg, info in missing.items():
        locations = ", ".join(info.get("files", []))
        section.entries.append(
            ReportEntry(
                path="word_addin_dev",
                type="npm-missing",
                reason=f"Module '{pkg}' is required but not installed (depcheck).",
                evidence=f"Referenced from: {locations}",
                suggested_action="Install the dependency or update imports to point at existing modules.",
                confidence="High",
            )
        )

    if not (unused_deps or unused_devdeps or missing):
        section.notes.append("depcheck reported no unused or missing dependencies.")


def collect_ts_test_files() -> List[Path]:
    patterns = ["*.spec.ts", "*.test.ts", "*.spec.tsx", "*.test.tsx"]
    results: List[Path] = []
    for pattern in patterns:
        results.extend(TS_APP_DIR.rglob(pattern))
    return sorted(set(results))


def gather_vitest_list(section: Section, all_tests: List[Path]) -> Tuple[List[Path], Optional[str]]:
    cmd = ["npx", "--yes", "vitest", "list", "--config", "vitest.config.ts"]
    rc, stdout, stderr = run_command(cmd, cwd=TS_PROJECT)
    if rc not in (0, 1):
        section.entries.append(
            ReportEntry(
                path="word_addin_dev",
                type="vitest-list",
                reason="vitest list failed",
                evidence=stderr.strip() or stdout.strip() or f"Exit code {rc}",
                suggested_action="Run vitest list manually with a supported Node version (>=20 <21).",
                confidence="Medium",
            )
        )
        return [], stderr or stdout

    discovered: List[Path] = []
    pattern = re.compile(r"app[\\/].+?\.(?:spec|test)\.tsx?")
    for match in pattern.finditer(stdout):
        candidate = (TS_PROJECT / match.group(0)).resolve()
        discovered.append(candidate)

    if not discovered:
        section.entries.append(
            ReportEntry(
                path="word_addin_dev",
                type="vitest-list",
                reason="vitest list returned no discovered test files",
                evidence=stdout.strip() or stderr.strip() or "No test files reported",
                suggested_action="Verify vitest include globs and Node runtime; all tests may be skipped in CI.",
                confidence="Medium",
            )
        )

    return sorted(set(discovered)), stdout + stderr


def gather_ts_orphans(section: Section) -> None:
    all_tests = collect_ts_test_files()
    discovered, raw_output = gather_vitest_list(section, all_tests)
    discovered_set = set(discovered)

    for test_file in all_tests:
        if test_file not in discovered_set:
            rel = test_file.relative_to(REPO_ROOT)
            section.entries.append(
                ReportEntry(
                    path=str(rel),
                    type="test-not-discovered",
                    reason="Test file is not returned by 'vitest list'.",
                    evidence=f"vitest list output lacked {rel}",
                    suggested_action="Align vitest include patterns so this spec participates in CI runs.",
                    confidence="Medium",
                )
            )

    # Orphan snapshots (Vitest)
    snapshot_files = list(TS_PROJECT.rglob("*.snap"))
    for snap in snapshot_files:
        source_candidate = Path(str(snap).replace(".snap", ""))
        if not source_candidate.exists():
            section.entries.append(
                ReportEntry(
                    path=str(snap.relative_to(REPO_ROOT)),
                    type="snapshot-orphan",
                    reason="Snapshot file has no matching test source.",
                    evidence=f"Expected companion test at {source_candidate}",
                    suggested_action="Confirm snapshot is needed or archive it.",
                    confidence="High",
                )
            )

    if not snapshot_files:
        section.notes.append("No Vitest snapshot (*.snap) files found under word_addin_dev.")

    # Identify vi.mock overrides to highlight heavy mocking
    vi_mock_pattern = re.compile(r"vi\.mock\((['\"])(.+?)\1")
    for test_file in all_tests:
        text = test_file.read_text(encoding="utf-8", errors="ignore")
        for match in vi_mock_pattern.finditer(text):
            target = match.group(2)
            section.entries.append(
                ReportEntry(
                    path=str(test_file.relative_to(REPO_ROOT)),
                    type="test-mock-alias",
                    reason=f"Test replaces '{target}' via vi.mock().",
                    evidence=match.group(0),
                    suggested_action="Document mocked modules or add explicit integration coverage to reduce false positives.",
                    confidence="Low",
                )
            )


def gather_python_vulture(section: Section) -> None:
    exclude = "word_addin_dev,node_modules,.git,__pycache__,reports,contract_ai_tree.txt"
    cmd = [
        sys.executable,
        "-m",
        "vulture",
        str(REPO_ROOT),
        "--min-confidence",
        "65",
        "--exclude",
        exclude,
    ]
    rc, stdout, stderr = run_command(cmd, cwd=REPO_ROOT)
    if rc not in (0, 1, 2, 3):
        section.notes.append(f"vulture failed (exit {rc}): {stderr.strip() or stdout.strip() or 'no output'}")
        return
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in lines:
        if ":" not in line:
            continue
        file_part, rest = line.split(":", 1)
        rel_path = os.path.relpath(file_part, REPO_ROOT)
        confidence = "High" if "100%" in rest else "Medium"
        section.entries.append(
            ReportEntry(
                path=rel_path,
                type="python-unused",
                reason=rest.strip(),
                evidence=line,
                suggested_action="Remove dead code or mark it as intentionally retained (e.g., via noqa).",
                confidence=confidence,
            )
        )

    if not lines:
        section.notes.append("vulture reported no unused Python symbols at >=65% confidence.")


def get_python_import_names(dist_name: str) -> List[str]:
    try:
        dist = importlib_metadata.distribution(dist_name)
    except importlib_metadata.PackageNotFoundError:
        return [dist_name.replace("-", "_")]
    top_level = dist.read_text("top_level.txt")
    if not top_level:
        return [dist_name.replace("-", "_")]
    names = [line.strip() for line in top_level.splitlines() if line.strip()]
    if not names:
        names = [dist_name.replace("-", "_")]
    return names


def ripgrep_import_exists(module: str) -> bool:
    pattern = rf"(from|import)\s+{re.escape(module)}\b"
    cmd = [
        "rg",
        "--hidden",
        "--max-count",
        "1",
        "-g",
        "!node_modules/**",
        "-g",
        "!word_addin_dev/**",
        "-g",
        "!reports/**",
        pattern,
        str(REPO_ROOT),
    ]
    rc, _, _ = run_command(cmd, cwd=REPO_ROOT)
    return rc == 0


def gather_python_deps(section: Section) -> None:
    try:
        from pip_chill import chill
    except ImportError:
        section.notes.append("pip-chill is not available; skipped Python dependency sweep.")
        return
    roots, _ = chill()
    for dist in roots:
        modules = get_python_import_names(dist.name)
        if any(ripgrep_import_exists(module) for module in modules):
            continue
        section.entries.append(
            ReportEntry(
                path="requirements.txt",
                type="python-dependency",
                reason=f"Package '{dist.name}' is installed but no imports were found (modules: {', '.join(modules)}).",
                evidence="ripgrep found no import hits",
                suggested_action="Confirm the dependency is needed; consider moving to optional or removing it.",
                confidence="Medium",
            )
        )


ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".css", ".js", ".ico", ".woff", ".woff2", ".ttf", ".otf"}


def gather_assets(section: Section) -> None:
    asset_roots = [REPO_ROOT / "word_addin_dev" / "app" / "assets", REPO_ROOT / "assets"]
    for root in asset_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() or path.suffix.lower() not in ASSET_EXTENSIONS:
                continue
            rel = path.relative_to(REPO_ROOT)
            search_term = path.name
            cmd = [
                "rg",
                "--glob",
                "!node_modules/**",
                "--glob",
                "!reports/**",
                "--count",
                search_term,
                str(REPO_ROOT),
            ]
            rc, stdout, _ = run_command(cmd, cwd=REPO_ROOT)
            hits = 0
            if stdout:
                try:
                    hits = sum(int(line.split(":")[-1]) for line in stdout.splitlines())
                except ValueError:
                    hits = 0
            if rc != 0 or hits <= 1:  # only the asset file itself often matches once
                section.entries.append(
                    ReportEntry(
                        path=str(rel),
                        type="asset-orphan",
                        reason="Asset file has no references in code or configs.",
                        evidence=f"ripgrep '{search_term}' returned {hits} hits",
                        suggested_action="Confirm the asset is unused; consider archiving or documenting usage.",
                        confidence="High",
                    )
                )


def gather_workflows(section: Section) -> None:
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        section.notes.append("No GitHub workflows directory present.")
        return
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover - PyYAML missing
        section.notes.append("PyYAML unavailable; workflow parsing skipped.")
        return

    for wf_path in sorted(workflows_dir.glob("*.yml")):
        with wf_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        triggers = data.get("on", {})
        trigger_desc = ", ".join(triggers.keys()) if isinstance(triggers, dict) else str(triggers)
        jobs = data.get("jobs", {}) or {}
        if not jobs:
            section.entries.append(
                ReportEntry(
                    path=str(wf_path.relative_to(REPO_ROOT)),
                    type="workflow",
                    reason="Workflow has no jobs configured.",
                    evidence=f"Triggers: {trigger_desc or 'n/a'}",
                    suggested_action="Populate jobs or remove the workflow.",
                    confidence="High",
                )
            )
            continue

        for job_name, job_def in jobs.items():
            suspicious: List[str] = []
            steps = job_def.get("steps", []) if isinstance(job_def, dict) else []
            for step in steps:
                run_cmd = step.get("run") if isinstance(step, dict) else None
                if not run_cmd:
                    continue
                suspicious.extend(find_missing_paths(run_cmd))
            reason = "Potential issues" if suspicious else "Manual trigger history unknown"
            evidence_parts = []
            if trigger_desc:
                evidence_parts.append(f"trigger={trigger_desc}")
            if suspicious:
                evidence_parts.append("missing: " + "; ".join(suspicious))
            else:
                evidence_parts.append("last_run=unknown (requires GitHub API)")
            section.entries.append(
                ReportEntry(
                    path=f"{wf_path.relative_to(REPO_ROOT)}::{job_name}",
                    type="workflow-job",
                    reason=reason,
                    evidence="; ".join(evidence_parts),
                    suggested_action="Check GitHub Actions history and validate referenced scripts exist.",
                    confidence="High" if suspicious else "Low",
                )
            )


def find_missing_paths(run_snippet: str) -> List[str]:
    candidates: List[str] = []
    pattern = re.compile(r"(?:python|py|pwsh|bash|sh)\s+([./][-\w./\\]+)")
    for match in pattern.finditer(run_snippet):
        raw = match.group(1)
        # Skip python -m usage
        if raw.startswith("-m"):
            continue
        normalized = raw.strip().strip("'\"")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        path = (REPO_ROOT / normalized).resolve()
        if not path.exists():
            candidates.append(normalized)
    return candidates


def gather_big_files(section: Section) -> None:
    big_files: List[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if (
            path.is_file()
            and path.stat().st_size >= 1_000_000
            and "node_modules" not in path.parts
            and "reports" not in path.parts
            and ".git" not in path.parts
        ):
            big_files.append(path)
    for path in sorted(big_files):
        rel = path.relative_to(REPO_ROOT)
        base = path.name
        size_mb = path.stat().st_size / (1024 * 1024)
        modified = git_last_modified(rel)
        reference_count = count_name_references(base)
        section.entries.append(
            ReportEntry(
                path=str(rel),
                type="large-file",
                reason=f"File size {size_mb:.2f} MB",
                evidence=f"last_modified={modified or 'unknown'}, name references={reference_count}",
                suggested_action="Confirm this belongs to active sources; otherwise move to _archive/.",
                confidence="Medium",
            )
        )

    root_docs = [p for p in REPO_ROOT.glob("*.docx")]
    root_docs += [p for p in REPO_ROOT.glob("*.pdf")]
    for doc in root_docs:
        section.entries.append(
            ReportEntry(
                path=str(doc.relative_to(REPO_ROOT)),
                type="doc-asset",
                reason="Office/PDF fixture stored at repository root.",
                evidence="Consider relocating to tests/fixtures or _archive.",
                suggested_action="Move to tests/fixtures or _archive/YYYY-MM for clarity.",
                confidence="Medium",
            )
        )


def git_last_modified(rel_path: Path) -> Optional[str]:
    cmd = ["git", "log", "-1", "--format=%cs", str(rel_path)]
    rc, stdout, _ = run_command(cmd, cwd=REPO_ROOT)
    if rc == 0:
        return stdout.strip() or None
    return None


def count_name_references(name: str) -> int:
    cmd = [
        "rg",
        "--hidden",
        "--glob",
        "!node_modules/**",
        "--glob",
        "!reports/**",
        "--glob",
        "!word_addin_dev/node_modules/**",
        name,
        str(REPO_ROOT),
    ]
    rc, stdout, _ = run_command(cmd, cwd=REPO_ROOT)
    if rc != 0 or not stdout:
        return 0
    total = 0
    for line in stdout.splitlines():
        try:
            total += int(line.split(":")[-1])
        except ValueError:
            total += 1
    return total


DOM_PATTERNS = (
    re.compile(r"document\\."),
    re.compile(r"window\\."),
    re.compile(r"DOMParser"),
)


def gather_fragile_tests(section: Section) -> None:
    fragile_candidates = [
        TS_PROJECT / "app" / "__tests__" / "bundle_no_raw_comments.test.ts",
        TS_PROJECT / "app" / "__tests__" / "requirement.sets.spec.ts",
    ]
    for path in fragile_candidates:
        if not path.exists():
            continue
        rel = path.relative_to(REPO_ROOT)
        if "bundle_no_raw_comments" in path.name:
            section.entries.append(
                ReportEntry(
                    path=str(rel),
                    type="fragile-test",
                    reason="Test asserts hard-coded counts of Office comment API usage in built bundle.",
                    evidence="Counts insertComment/comments.add occurrences; bundle changes will break expectation.",
                    suggested_action="Check for behavior-based assertions (e.g., stub notifier) instead of raw regex counts.",
                    confidence="Medium",
                )
            )
        elif "requirement.sets" in path.name:
            section.entries.append(
                ReportEntry(
                    path=str(rel),
                    type="fragile-test",
                    reason="Test enforces specific disabled=true DOM state for mocked requirement sets.",
                    evidence="Global Office mocks + direct DOM queries can desync from production behavior.",
                    suggested_action="Assert high-level capability toggles rather than individual button.disabled flags.",
                    confidence="Medium",
                )
            )

    dom_bound_tests = []
    for test_file in TS_PROJECT.rglob("*.spec.ts"):
        text = test_file.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in DOM_PATTERNS):
            dom_bound_tests.append(test_file)
    for test_file in sorted(set(dom_bound_tests)):
        rel = test_file.relative_to(REPO_ROOT)
        section.entries.append(
            ReportEntry(
                path=str(rel),
                type="dom-dependent-test",
                reason="Test relies on DOM globals and will fail without a shared skeleton.",
                evidence="References document/window directly.",
                suggested_action="Extract shared mountPanelSkeleton() helper to initialise DOM fixtures before assertions.",
                confidence="Low",
            )
        )


def build_summary(sections: Dict[str, Section]) -> Dict[str, object]:
    all_entries = [entry for section in sections.values() for entry in section.entries]
    confidence_counts = Counter(entry.confidence for entry in all_entries)
    return {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "total_findings": len(all_entries),
        "confidence_breakdown": dict(confidence_counts),
        "sections": {key: len(sections[key].entries) for key in sections},
    }


def write_markdown(sections: Dict[str, Section], summary: Dict[str, object]) -> None:
    lines: List[str] = []
    lines.append("# Garbage Sweep Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("- Generated at: ``{}``".format(summary["generated_at"]))
    lines.append("- Total findings: **{}**".format(summary["total_findings"]))
    confidence = summary.get("confidence_breakdown", {})
    if confidence:
        lines.append("- Confidence levels: " + ", ".join(f"{k}: {v}" for k, v in confidence.items()))
    lines.append("")

    for key in SECTION_ORDER:
        section = sections.get(key)
        if not section:
            continue
        lines.append(f"## {section.title}")
        lines.append("")
        if section.notes:
            for note in section.notes:
                lines.append(f"- _Note_: {note}")
            lines.append("")
        if not section.entries:
            lines.append("No findings.")
            lines.append("")
            continue
        lines.append("| Path | Type | Reason | Evidence | Suggested action | Confidence |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for entry in section.entries:
            row = [escape_markdown(cell) for cell in entry.to_row()]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape_markdown(text: str) -> str:
    return text.replace("|", "\\|")


def write_json(sections: Dict[str, Section], summary: Dict[str, object]) -> None:
    payload = {
        "summary": summary,
        "sections": {key: sections[key].to_dict() for key in sections},
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run garbage sweep checks and build reports.")
    parser.add_argument("--no-ts", action="store_true", help="Skip TypeScript analyses")
    parser.add_argument("--no-python", action="store_true", help="Skip Python analyses")
    parser.add_argument("--no-assets", action="store_true", help="Skip asset scans")
    parser.add_argument("--no-workflows", action="store_true", help="Skip workflow audit")
    parser.add_argument("--no-files", action="store_true", help="Skip large file scan")
    parser.add_argument("--no-fragile", action="store_true", help="Skip fragile test heuristics")
    args = parser.parse_args(argv)

    ensure_reports_dir()

    sections: Dict[str, Section] = {}
    if not args.no_ts:
        gather_ts_unused_exports(add_section(sections, "unused_exports", "Unused exports (TypeScript)"))
        gather_ts_depcheck(add_section(sections, "unused_dependencies", "Unused dependencies (TS/Python)"))
        gather_ts_orphans(add_section(sections, "orphan_tests_and_snapshots", "Orphan tests & snapshots"))
    if not args.no_python:
        gather_python_vulture(add_section(sections, "unused_dependencies", "Unused dependencies (TS/Python)"))
        gather_python_deps(add_section(sections, "unused_dependencies", "Unused dependencies (TS/Python)"))
    if not args.no_assets:
        gather_assets(add_section(sections, "orphan_assets", "Orphan assets"))
    if not args.no_workflows:
        gather_workflows(add_section(sections, "workflows", "Workflow issues"))
    if not args.no_files:
        gather_big_files(add_section(sections, "big_files", "Big files"))
    if not args.no_fragile:
        gather_fragile_tests(add_section(sections, "fragile_tests", "Fragile tests"))

    summary = build_summary(sections)
    write_markdown(sections, summary)
    write_json(sections, summary)
    print(f"Report written to {REPORT_MD} and {REPORT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
