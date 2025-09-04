from __future__ import annotations

from html import escape
from typing import Any, Dict


def render_html_report(trace: Dict[str, Any]) -> str:
    analysis = trace.get("analysis", {}) or {}
    findings = analysis.get("findings") or []
    risk_counts: Dict[str, int] = {}
    for f in findings:
        sev = str(f.get("severity") or f.get("severity_level") or "info").lower()
        risk_counts[sev] = risk_counts.get(sev, 0) + 1
    rc_list = "".join(f"<li>{escape(k)}: {v}</li>" for k, v in risk_counts.items()) or "<li>no findings</li>"
    rows = []
    for f in findings:
        sev = escape(str(f.get("severity") or f.get("severity_level") or ""))
        rule = escape(str(f.get("rule_id") or f.get("code") or ""))
        excerpt = escape(str(f.get("excerpt") or f.get("text") or ""))
        advice = escape(str(f.get("advice") or f.get("recommendation") or ""))
        rows.append(f"<tr><td>{sev}</td><td>{rule}</td><td>{excerpt}</td><td>{advice}</td></tr>")
    findings_html = "".join(rows) or "<tr><td colspan='4'>No findings</td></tr>"
    meta = trace.get("meta", {}) or {}
    header = (
        f"<div><b>CID:</b> {escape(trace.get('cid',''))} | "
        f"<b>Created:</b> {escape(trace.get('created_at',''))} | "
        f"<b>Model:</b> {escape(str(meta.get('model','')))}</div>"
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Contract AI Report</title>
<style>body{{font-family:Arial, sans-serif;margin:20px;}}
 table{{border-collapse:collapse;width:100%;}}
 th,td{{border:1px solid #ccc;padding:4px;text-align:left;}}
 th{{background:#eee;}}</style></head><body>
<h1>Contract AI Report</h1>
{header}
<h2>Risk counts</h2>
<ul>{rc_list}</ul>
<h2>Findings</h2>
<table><thead><tr><th>Severity</th><th>Rule</th><th>Excerpt</th><th>Advice</th></tr></thead>
<tbody>{findings_html}</tbody></table>
</body></html>"""
    return html
