#!/usr/bin/env python3
"""Manual smoke test covering Analyze + TRACE bridge."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from typing import Any

import requests


def _payload() -> dict[str, Any]:
    return {
        "text": (
            "Payment terms: invoices due within 30 days. "
            "Governing Law: England and Wales. "
            "Confidentiality shall survive termination for 3 years. "
        )
    }


def _headers() -> dict[str, str]:
    schema = os.getenv("TRACE_SMOKE_SCHEMA", "1.4")
    api_key = os.getenv("TRACE_SMOKE_API_KEY", "local-test-key-123")
    return {"x-api-key": api_key, "x-schema-version": schema}


def main() -> int:
    backend = os.getenv("BACKEND_URL", "http://127.0.0.1:9443").rstrip("/")
    analyze_url = f"{backend}/api/analyze"

    try:
        analyze_resp = requests.post(analyze_url, json=_payload(), headers=_headers(), timeout=30)
    except Exception as exc:  # pragma: no cover - manual tool
        print(f"[smoke] POST {analyze_url} failed: {exc}")
        return 1

    if analyze_resp.status_code != HTTPStatus.OK:
        print(f"[smoke] analyze failed: {analyze_resp.status_code} {analyze_resp.text}")
        return 1

    cid = analyze_resp.headers.get("x-cid")
    if not cid:
        try:
            cid = analyze_resp.json().get("cid")
        except Exception:
            cid = None
    if not cid:
        print("[smoke] analyze succeeded but cid missing")
        return 1

    trace_url = f"{backend}/api/trace/{cid}"
    print(f"[smoke] analyze ok, cid={cid}")
    print(f"[smoke] trace html: {trace_url}.html")

    try:
        trace_resp = requests.get(trace_url, timeout=30)
    except Exception as exc:  # pragma: no cover - manual tool
        print(f"[smoke] GET {trace_url} failed: {exc}")
        return 1

    if trace_resp.status_code != HTTPStatus.OK:
        print(f"[smoke] trace fetch failed: {trace_resp.status_code} {trace_resp.text}")
        return 1

    try:
        trace = trace_resp.json()
    except json.JSONDecodeError as exc:
        print(f"[smoke] trace returned non-JSON payload: {exc}")
        return 1

    coverage = trace.get("coverage") or {}
    meta = (trace.get("meta") or {}).get("timings_ms") or {}
    zones_total = coverage.get("zones_total")
    zones_fired = coverage.get("zones_fired")
    merge_ms = meta.get("merge_ms")

    print("[smoke] coverage:", zones_fired, "/", coverage.get("zones_present"), "/", zones_total)
    print("[smoke] merge_ms:", merge_ms)

    return 0


if __name__ == "__main__":  # pragma: no cover - script entry
    raise SystemExit(main())
