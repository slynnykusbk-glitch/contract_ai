from __future__ import annotations

from .schemas import MetricsResponse


def render_metrics_html(resp: MetricsResponse) -> str:
    m = resp.metrics
    lines = ["<html><body>", "<h1>Quality metrics</h1>"]
    lines.append("<table><tr><th>rule_id</th><th>tp</th><th>fp</th><th>fn</th><th>precision</th><th>recall</th><th>f1</th></tr>")
    for r in m.rules:
        lines.append(
            f"<tr><td>{r.rule_id}</td><td>{r.tp}</td><td>{r.fp}</td><td>{r.fn}</td>"
            f"<td>{r.precision:.3f}</td><td>{r.recall:.3f}</td><td>{r.f1:.3f}</td></tr>"
        )
    lines.append("</table>")
    cov = m.coverage
    acc = m.acceptance
    perf = m.perf
    lines.append(
        f"<p>Coverage: {cov.coverage:.3f} ({cov.rules_fired}/{cov.rules_total})</p>"
    )
    lines.append(
        f"<p>Acceptance rate: {acc.acceptance_rate:.3f} ({acc.applied}/{acc.rejected})</p>"
    )
    lines.append(
        f"<p>Performance: {perf.avg_ms_per_page:.3f} ms/page over {perf.docs} docs</p>"
    )
    lines.append("</body></html>")
    return "".join(lines)
