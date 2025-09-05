from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from contract_review_app.legal_rules import loader


def main() -> None:
    loader.load_rule_packs()
    for pack in loader.loaded_packs():
        ids = ", ".join(pack.get("rule_ids", [])[:5])
        print(f"{pack['pack']}: {pack['rules_count']} rules -> {ids}")


if __name__ == "__main__":
    main()
