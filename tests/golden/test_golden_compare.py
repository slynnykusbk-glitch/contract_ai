from __future__ import annotations

import json
import os
import re
import time
import difflib
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION
from contract_review_app.utils.doc_loader import load_docx_text

from ._normalizer_local import canonical_json, normalize_response
from .util_docx import load_valid_docx


MIN_VALID = 15

DOCS_DIR = Path(__file__).parent / "docs"
BASELINE_DIR = Path(__file__).parent / "baseline"
REPORT_DIR = Path("var/reports/golden_diff")
PAGE_RE = re.compile(r"_(\d+)_pages", re.IGNORECASE)
SLA_SECONDS = {5: 1.2, 50: 6.0, 200: 25.0}

ALL_VALID_DOCS = load_valid_docx(DOCS_DIR)
VALID_WITH_BASELINE = [
    p for p in ALL_VALID_DOCS if (BASELINE_DIR / f"{p.stem}.json").exists()
]

@pytest.fixture(scope="session")
def api_client() -> TestClient:
    os.environ.setdefault("AZURE_OPENAI_API_KEY", "local-test-key-123")
    os.environ.setdefault("FEATURE_COMPANIES_HOUSE", "0")
    return TestClient(app)


def _pages_for(path: Path) -> int:
    match = PAGE_RE.search(path.stem)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    raise AssertionError(f"Unable to determine page count from file name: {path.name}")


def _assert_schema_v14(payload: Dict[str, Any], *, require_provider: bool = False) -> None:
    assert payload.get("schema_version") == SCHEMA_VERSION
    assert isinstance(payload.get("status"), str)

    analysis = payload.get("analysis")
    assert isinstance(analysis, dict)
    findings = analysis.get("findings")
    assert isinstance(findings, list)
    for finding in findings:
        assert isinstance(finding, dict)
        assert isinstance(finding.get("rule_id"), str)
        assert isinstance(finding.get("severity"), str)
        assert isinstance(finding.get("law_refs"), list)

    results = payload.get("results")
    assert isinstance(results, dict)
    res_summary = results.get("summary")
    assert isinstance(res_summary, dict)
    res_analysis = results.get("analysis")
    if res_analysis is None:
        res_analysis = {}
    assert isinstance(res_analysis, dict)
    assert isinstance(res_analysis.get("findings", []), list)

    summary = payload.get("summary")
    assert isinstance(summary, dict)

    meta = payload.get("meta")
    assert isinstance(meta, dict)
    provider = meta.get("provider")
    model = meta.get("model")
    if require_provider:
        assert isinstance(provider, str)
        assert isinstance(model, str)
    else:
        if provider is not None:
            assert isinstance(provider, str)
        if model is not None:
            assert isinstance(model, str)
    assert isinstance(meta.get("language"), str)

    coverage = payload.get("rules_coverage")
    assert isinstance(coverage, dict)
    assert isinstance(coverage.get("doc_type"), dict)
    assert isinstance(coverage.get("rules"), list)

    assert isinstance(payload.get("findings"), list)
    assert isinstance(payload.get("recommendations"), list)


def _is_subset(expected: Any, current: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(current, dict):
            return False
        for key, exp_value in expected.items():
            if key not in current:
                return False
            if not _is_subset(exp_value, current[key]):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(current, list):
            return False
        used = [False] * len(current)
        for exp_item in expected:
            match_found = False
            for idx, cur_item in enumerate(current):
                if not used[idx] and _is_subset(exp_item, cur_item):
                    used[idx] = True
                    match_found = True
                    break
            if not match_found:
                return False
        return True
    return expected == current
def _post_analyze(client: TestClient, text: str) -> Dict[str, Any]:
    response = client.post(
        "/api/analyze",
        json={"text": text, "mode": "live"},
        headers={"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_normalizer_is_deterministic(api_client: TestClient) -> None:
    if len(ALL_VALID_DOCS) < MIN_VALID:
        pytest.skip(
            f"Not enough valid DOCX ({len(ALL_VALID_DOCS)}<{MIN_VALID}); skipping."
        )

    sample_text = load_docx_text(str(ALL_VALID_DOCS[0]))
    payload = _post_analyze(api_client, sample_text)
    _assert_schema_v14(payload, require_provider=True)
    norm_first = normalize_response(payload)
    norm_second = normalize_response(norm_first)
    assert norm_first == norm_second


@pytest.mark.timeout(180)
def test_suite_against_golden(api_client: TestClient, request: pytest.FixtureRequest) -> None:
    if len(ALL_VALID_DOCS) < MIN_VALID:
        pytest.skip(
            f"Not enough valid DOCX ({len(ALL_VALID_DOCS)}<{MIN_VALID}); skipping."
        )

    generate = bool(request.config.getoption("--generate-golden"))

    if not generate and len(VALID_WITH_BASELINE) < MIN_VALID:
        pytest.skip(
            f"Not enough baselines for valid DOCX ({len(VALID_WITH_BASELINE)}<{MIN_VALID}); skipping."
        )

    docs = ALL_VALID_DOCS if generate else VALID_WITH_BASELINE
    diff_builder = difflib.HtmlDiff(tabsize=2, wrapcolumn=120)
    report_sections: List[str] = []
    failures: List[str] = []
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    for doc_path in docs:
        baseline_path = BASELINE_DIR / f"{doc_path.stem}.json"
        pages = _pages_for(doc_path)
        text = load_docx_text(str(doc_path))

        started = time.perf_counter()
        payload = _post_analyze(api_client, text)
        duration = time.perf_counter() - started

        limit = SLA_SECONDS.get(pages)
        sla_note = ""
        if limit is not None and duration > limit:
            sla_note = f" (SLA {limit:.2f}s breached)"
        print(f"[golden] {doc_path.name}: {duration:.2f}s for {pages} pages{sla_note}")

        _assert_schema_v14(payload, require_provider=True)
        normalized = normalize_response(payload)
        assert normalize_response(normalized) == normalized
        current_json = canonical_json(normalized)

        if generate:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(current_json, encoding="utf-8")
            report_sections.append(
                f"<h2>{doc_path.name}</h2><p>Golden snapshot regenerated.</p>"
            )
            continue

        if not baseline_path.exists():
            raise AssertionError(f"Missing golden baseline for {doc_path.name}")

        golden_json = baseline_path.read_text(encoding="utf-8")
        golden_payload = json.loads(golden_json)
        _assert_schema_v14(golden_payload)
        golden_payload = normalize_response(golden_payload)

        assert _is_subset(golden_payload, normalized), (
            f"Golden snapshot for {doc_path.name} is not a subset of current response"
        )

        golden_canonical = canonical_json(golden_payload)
        if golden_canonical != golden_json:
            # Normalise legacy snapshots on the fly before diffing
            golden_json = golden_canonical

        if golden_json == current_json:
            report_sections.append(
                f"<h2>{doc_path.name}</h2><p>No differences.</p>"
            )
            continue

        diff_table = diff_builder.make_table(
            golden_json.splitlines(),
            current_json.splitlines(),
            fromdesc=f"golden:{doc_path.name}",
            todesc="current",
            context=True,
            numlines=4,
        )
        report_sections.append(
            f"<h2>{doc_path.name}</h2>" + diff_table
        )
        failures.append(doc_path.name)

    report_html = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>Golden diff report</title>
  <style>
    body {{ font-family: Arial, sans-serif; }}
    table.diff {{ font-family: Courier, monospace; border: 1px solid #888; }}
    table.diff th {{ background: #eee; padding: 4px; }}
    table.diff td {{ padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>/api/analyze golden comparison</h1>
  {sections}
</body>
</html>
""".strip().format(sections="\n".join(report_sections))
    (REPORT_DIR / "index.html").write_text(report_html, encoding="utf-8")
    if failures:
        raise AssertionError(
            "Golden diffs detected for: " + ", ".join(sorted(failures))
        )
