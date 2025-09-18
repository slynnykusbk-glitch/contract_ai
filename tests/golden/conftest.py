from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--generate-golden",
        action="store_true",
        help="Regenerate golden snapshots instead of asserting diffs.",
    )
