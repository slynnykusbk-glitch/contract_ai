from contract_review_app.core.schemas import AnalysisOutput
from jinja2 import Template
import webbrowser
from typing import Any, Mapping, Sequence


def generate_report(
    results: list[AnalysisOutput], output_file: str = "contract_report.html"
) -> None:
    """
    Генерує HTML-звіт і відкриває його у браузері.
    """
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Contract Analysis Report</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            h1 { color: #2E4053; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #2E86C1; color: white; }
            .ok { color: green; font-weight: bold; }
            .fail { color: red; font-weight: bold; }
            .warn { color: orange; font-weight: bold; }
            .code { font-family: monospace; }
        </style>
    </head>
    <body>
        <h1>📄 Contract Analysis Report</h1>
        <table>
            <tr>
                <th>Clause</th>
                <th>Status</th>
                <th>Risk Level</th>
                <th>Score</th>
                <th>Category</th>
                <th>Findings</th>
                <th>Recommendations</th>
                <th>Citations</th>
                <th>Diagnostics</th>
                <th>Trace</th>
            </tr>
            {% for clause in results %}
            <tr>
                <td>{{ clause.clause_type }}</td>
                <td class="{{ clause.status|lower }}">{{ clause.status }}</td>
                <td>{{ clause.risk_level or '—' }}</td>
                <td>{{ clause.score or '—' }}</td>
                <td>{{ clause.category or '—' }}</td>
                <td>
                    {% for f in clause.findings %}
                        <div class="code">{{ f.code }}</div>
                        <div>{{ f.message }}</div>
                        <div><i>{{ f.severity }}</i></div>
                        <div>{{ f.evidence }}</div>
                        <div><small>{{ f.legal_basis|join(", ") }}</small></div>
                        <hr>
                    {% endfor %}
                </td>
                <td>
                    {% for r in clause.recommendations %}
                        <li>{{ r }}</li>
                    {% endfor %}
                </td>
                <td>
                    {% for c in clause.citations %}
                        <a href="{{ c }}" target="_blank">{{ c }}</a><br>
                    {% endfor %}
                </td>
                <td>
                    <pre>{{ clause.diagnostics }}</pre>
                </td>
                <td>
                    <small>{{ clause.trace|join(" → ") }}</small>
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """
    html = Template(template).render(results=results)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Report generated: {output_file}")
    webbrowser.open(output_file)


def render(report_context: Any) -> str:
    """
    Адаптер під тести:
    - приймає dict із ключем 'results' або список AnalysisOutput
    - повертає HTML-рядок (без відкриття браузера)
    """
    if isinstance(report_context, Mapping):
        ctx = dict(report_context)
        results = ctx.get("results")
        if results is None and isinstance(ctx.get("clauses"), Sequence):
            ctx["results"] = ctx["clauses"]
    elif isinstance(report_context, Sequence):
        ctx = {"results": list(report_context)}
    else:
        ctx = {"results": []}

    template = """
    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>Contract Analysis Report</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 20px; }
      h1 { color: #2E4053; }
      table { border-collapse: collapse; width: 100%; margin-top: 20px; }
      th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
      th { background-color: #2E86C1; color: white; }
      .ok { color: green; font-weight: bold; }
      .fail { color: red; font-weight: bold; }
      .warn { color: orange; font-weight: bold; }
      .code { font-family: monospace; }
    </style></head><body>
      <h1>📄 Contract Analysis Report</h1>
      <table>
        <tr>
          <th>Clause</th><th>Status</th><th>Risk Level</th><th>Score</th><th>Category</th>
          <th>Findings</th><th>Recommendations</th><th>Citations</th><th>Diagnostics</th><th>Trace</th>
        </tr>
        {% for clause in results %}
        <tr>
          <td>{{ clause.clause_type }}</td>
          <td class="{{ clause.status|lower }}">{{ clause.status }}</td>
          <td>{{ clause.risk_level or '—' }}</td>
          <td>{{ clause.score or '—' }}</td>
          <td>{{ clause.category or '—' }}</td>
          <td>
            {% for f in clause.findings %}
              <div class="code">{{ f.code }}</div>
              <div>{{ f.message }}</div>
              <div><i>{{ f.severity }}</i></div>
              <div>{{ f.evidence }}</div>
              <div><small>{{ f.legal_basis|join(", ") }}</small></div>
              <hr>
            {% endfor %}
          </td>
          <td>{% for r in clause.recommendations %}<li>{{ r }}</li>{% endfor %}</td>
          <td>{% for c in clause.citations %}<a href="{{ c }}" target="_blank">{{ c }}</a><br>{% endfor %}</td>
          <td><pre>{{ clause.diagnostics }}</pre></td>
          <td><small>{{ clause.trace|join(" → ") }}</small></td>
        </tr>
        {% endfor %}
      </table>
    </body></html>
    """
    return Template(template).render(results=ctx.get("results", []))
