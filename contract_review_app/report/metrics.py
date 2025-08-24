from __future__ import annotations
from typing import Dict, Any, List


def summarize_statuses(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    ok = sum(1 for r in results if (r.get("status") or "").upper() == "OK")
    warn = sum(1 for r in results if (r.get("status") or "").upper() == "WARN")
    fail = sum(1 for r in results if (r.get("status") or "").upper() == "FAIL")

    def pct(n):
        return (n * 100.0 / total) if total else 0.0

    return {
        "total": total,
        "ok": ok,
        "ok_pct": pct(ok),
        "warn": warn,
        "warn_pct": pct(warn),
        "fail": fail,
        "fail_pct": pct(fail),
    }
