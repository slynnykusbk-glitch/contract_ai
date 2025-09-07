from pathlib import Path
import json
import pytest

from insurance_checker import check

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def good_text() -> str:
    return load_fixture("good_master_excerpt.txt")
