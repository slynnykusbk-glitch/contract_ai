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
    out_path = Path(args.out) if args.out else None

    if args.csv:
        content = to_csv(resp.metrics.rules)
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
        else:
            print(content)
        return 0

    if args.html:
        html = render_metrics_html(resp)
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html, encoding="utf-8")
        else:
            print(html)
        return 0

    # default JSON
    data = json.loads(resp.model_dump_json())
    text = json.dumps(data, ensure_ascii=False)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
