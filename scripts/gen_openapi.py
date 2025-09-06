#!/usr/bin/env python3
"""Generate OpenAPI specification for Contract AI.

Writes ``openapi.json`` in the repository root.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contract_review_app.api.app import app


def main() -> None:
    spec = app.openapi()
    out = Path(__file__).resolve().parents[1] / "openapi.json"
    out.write_text(json.dumps(spec, indent=2))
    print(f"openapi.json written with {len(spec.get('paths', {}))} paths")


if __name__ == "__main__":
    main()
