from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compute import collect_metrics, to_csv
from .report_html import render_metrics_html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--csv", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    resp = collect_metrics()
    out_base = Path(args.out) if args.out else None

    # Always emit JSON if --json specified or no other flags provided
    if args.json or not (args.csv or args.html):
        data = json.loads(resp.model_dump_json())
        text = json.dumps(data, ensure_ascii=False)
        if out_base:
            out_base.parent.mkdir(parents=True, exist_ok=True)
            out_base.with_suffix(".json").write_text(text, encoding="utf-8")
        else:
            print(text)

    if args.csv:
        content = to_csv(resp.metrics.rules)
        if out_base:
            out_base.parent.mkdir(parents=True, exist_ok=True)
            out_base.with_suffix(".csv").write_text(content, encoding="utf-8")
        else:
            print(content)

    if args.html:
        html = render_metrics_html(resp)
        if out_base:
            out_base.parent.mkdir(parents=True, exist_ok=True)
            out_base.with_suffix(".html").write_text(html, encoding="utf-8")
        else:
            print(html)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
