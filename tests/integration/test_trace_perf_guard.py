from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Final

import pytest

from tests.integration.test_trace_flag_bootstrap import (
    _build_client,
    _cleanup,
    _headers,
)


_LOGGER = logging.getLogger(__name__)

_TRACE_SIZE_LIMIT: Final[int] = 1_500_000
_TRACE_FETCH_LIMIT_SECONDS: Final[float] = 1.5
_TARGET_DOCUMENT_SIZE_CHARS: Final[int] = 120_000
_TRACE_PER_ENTRY_LIMIT: Final[int] = 60_000
_EMPTY_RULE_DIR: Final[Path] = Path(__file__).resolve().parent / "data" / "empty_rules"
_EMPTY_RULE_DIR.mkdir(parents=True, exist_ok=True)

_TEMPLATE_PARAGRAPHS: Final[tuple[str, ...]] = (
    (
        "The agreement between the parties establishes obligations, remedies, and "
        "milestones that are meant to balance risk while keeping project momentum. "
        "Each revision of the specification must be communicated promptly so that "
        "both the vendor and the client remain aligned on deliverables and timelines."
    ),
    (
        "Operational continuity requires contingency planning, including redundant "
        "systems, periodic testing, and escalation paths for service interruptions. "
        "A disciplined approach to change management avoids regressions and "
        "maintains institutional knowledge across teams and jurisdictions."
    ),
    (
        "Compliance clauses reference international regulations, emphasizing "
        "transparency in how personal data is processed, transferred, and retained. "
        "Adequate safeguards, impact assessments, and record keeping are essential "
        "to satisfy auditors and regulators in the relevant territories."
    ),
    (
        "Financial terms describe invoicing schedules, tax responsibilities, and "
        "applicable remedies for late payments or currency fluctuations. The parties "
        "agree to cooperate in good faith to resolve disputes before initiating any "
        "formal arbitration or litigation procedures."
    ),
    (
        "Security appendices outline encryption standards, monitoring expectations, "
        "and incident response timelines so that stakeholders can rely on consistent "
        "protections. Training requirements are reiterated to ensure that operational "
        "staff recognize and report anomalous behaviors quickly."
    ),
)


def _make_long_document() -> str:
    sections: list[str] = []
    while len("\n\n".join(sections)) < _TARGET_DOCUMENT_SIZE_CHARS:
        index = len(sections)
        template = _TEMPLATE_PARAGRAPHS[index % len(_TEMPLATE_PARAGRAPHS)]
        sections.append(f"Section {index + 1}. {template}")
    return "\n\n".join(sections)


def _capture_trace_snapshot(document_text: str) -> dict[str, Any]:
    client = None
    modules: list[str] = []
    try:
        client, modules = _build_client("1")
        payload = {"text": document_text}
        analyze_response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert analyze_response.status_code == 200

        cid = analyze_response.headers.get("x-cid")
        assert cid

        start = time.perf_counter()
        trace_response = client.get(f"/api/trace/{cid}")
        fetch_duration = time.perf_counter() - start
        assert trace_response.status_code == 200

        trace_body = trace_response.json()
        trace_size = len(json.dumps(trace_body))

        dispatch_candidates = 0
        dispatch_payload = trace_body.get("dispatch")
        if isinstance(dispatch_payload, dict):
            candidates = dispatch_payload.get("candidates")
            if isinstance(candidates, list):
                dispatch_candidates = len(candidates)

        feature_segments = 0
        features_payload = trace_body.get("features")
        if isinstance(features_payload, dict):
            segments = features_payload.get("segments")
            if isinstance(segments, list):
                feature_segments = len(segments)

        return {
            "fetch_duration": fetch_duration,
            "size": trace_size,
            "dispatch_candidates": dispatch_candidates,
            "feature_segments": feature_segments,
        }
    finally:
        if client is not None:
            _cleanup(client, modules)


def test_trace_perf_guard() -> None:
    prev_rule_dirs = os.environ.get("RULE_PACKS_DIRS")
    prev_loader_module = sys.modules.get("contract_review_app.legal_rules.loader")
    os.environ["RULE_PACKS_DIRS"] = str(_EMPTY_RULE_DIR)
    client = None
    modules: list[str] = []
    try:
        sys.modules.pop("contract_review_app.legal_rules.loader", None)
        client, modules = _build_client("1")
        payload = {"text": _make_long_document()}
        analyze_response = client.post("/api/analyze", headers=_headers(), json=payload)
        assert analyze_response.status_code == 200

        cid = analyze_response.headers.get("x-cid")
        assert cid

        start = time.perf_counter()
        trace_response = client.get(f"/api/trace/{cid}")
        fetch_duration = time.perf_counter() - start

        assert trace_response.status_code == 200
        trace_body = trace_response.json()
        trace_len = len(json.dumps(trace_body))

        _LOGGER.info(
            "TRACE size/perf guard – chars: %s, fetch_time: %.3fs",
            trace_len,
            fetch_duration,
        )
        print(
            f"TRACE size/perf guard – chars: {trace_len}, fetch_time: {fetch_duration:.3f}s"
        )

        assert (
            trace_len <= _TRACE_SIZE_LIMIT
        ), f"Trace payload unexpectedly large: {trace_len} > {_TRACE_SIZE_LIMIT}"
        assert fetch_duration <= _TRACE_FETCH_LIMIT_SECONDS, (
            "Trace fetch slower than expected: "
            f"{fetch_duration:.3f}s > {_TRACE_FETCH_LIMIT_SECONDS:.3f}s"
        )
    finally:
        if client is not None:
            _cleanup(client, modules)
        if prev_rule_dirs is None:
            os.environ.pop("RULE_PACKS_DIRS", None)
        else:
            os.environ["RULE_PACKS_DIRS"] = prev_rule_dirs

        if prev_loader_module is not None:
            sys.modules["contract_review_app.legal_rules.loader"] = prev_loader_module
        else:
            importlib.invalidate_caches()
            importlib.import_module("contract_review_app.legal_rules.loader")


def test_trace_perf_guard_entry_limit() -> None:
    prev_rule_dirs = os.environ.get("RULE_PACKS_DIRS")
    prev_loader_module = sys.modules.get("contract_review_app.legal_rules.loader")
    prev_entry_limit = os.environ.get("TRACE_PER_ENTRY_MAX_BYTES")

    document_text = _make_long_document()
    os.environ["RULE_PACKS_DIRS"] = str(_EMPTY_RULE_DIR)

    try:
        os.environ.pop("TRACE_PER_ENTRY_MAX_BYTES", None)
        baseline = _capture_trace_snapshot(document_text)

        assert baseline["size"] > _TRACE_PER_ENTRY_LIMIT

        os.environ["TRACE_PER_ENTRY_MAX_BYTES"] = str(_TRACE_PER_ENTRY_LIMIT)
        limited = _capture_trace_snapshot(document_text)

        assert (
            limited["size"] <= _TRACE_PER_ENTRY_LIMIT
        ), f"Trace payload exceeds entry limit: {limited['size']} > {_TRACE_PER_ENTRY_LIMIT}"
        assert limited["size"] < baseline["size"]
        assert limited["dispatch_candidates"] <= baseline["dispatch_candidates"]
        assert limited["feature_segments"] <= baseline["feature_segments"]
        assert (
            limited["dispatch_candidates"] < baseline["dispatch_candidates"]
            or limited["feature_segments"] < baseline["feature_segments"]
        )
        assert limited["fetch_duration"] <= _TRACE_FETCH_LIMIT_SECONDS, (
            "Trace fetch slower than expected with entry limit: "
            f"{limited['fetch_duration']:.3f}s > {_TRACE_FETCH_LIMIT_SECONDS:.3f}s"
        )
    finally:
        if prev_entry_limit is None:
            os.environ.pop("TRACE_PER_ENTRY_MAX_BYTES", None)
        else:
            os.environ["TRACE_PER_ENTRY_MAX_BYTES"] = prev_entry_limit

        if prev_rule_dirs is None:
            os.environ.pop("RULE_PACKS_DIRS", None)
        else:
            os.environ["RULE_PACKS_DIRS"] = prev_rule_dirs

        if prev_loader_module is not None:
            sys.modules["contract_review_app.legal_rules.loader"] = prev_loader_module
        else:
            importlib.invalidate_caches()
            importlib.import_module("contract_review_app.legal_rules.loader")
