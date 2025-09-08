#!/usr/bin/env python
import json
import sys
from pathlib import Path
from fastapi.openapi.utils import get_openapi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contract_review_app.api.app import app


def main() -> None:
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    out_path = ROOT / "openapi.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, sort_keys=True, indent=2)


if __name__ == "__main__":
    main()
