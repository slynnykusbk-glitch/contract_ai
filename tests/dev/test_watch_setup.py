import importlib
import importlib.util
import os
from pathlib import Path

REPO_ROOT = (
    Path(__file__).resolve().parents[2]
)  # .../repo/contract_review_app/tests/dev/ -> repo


def test_watch_scripts_exist():
    tools = REPO_ROOT / "tools" / "watch_backend_tests.ps1"
    launcher = REPO_ROOT / "ContractAI-Watch-Tests.local.ps1"
    assert tools.exists(), f"{tools} must exist"
    assert launcher.exists(), f"{launcher} must exist"


def test_pytest_watch_installed():
    try:
        importlib.import_module("pytest_watch")
    except Exception as e:
        raise AssertionError(f"pytest-watch must be importable: {e}")


def test_pytest_ini_present_and_points_to_tests():
    ini = REPO_ROOT / "pytest.ini"
    assert ini.exists(), "pytest.ini must exist"
    content = ini.read_text(encoding="utf-8", errors="ignore")
    assert "testpaths" in content, "pytest.ini should define testpaths"
    # базовая проверка — твои тесты лежат в contract_review_app/tests
    assert "contract_review_app/tests" in content.replace(
        "\\", "/"
    ), "pytest.ini must include contract_review_app/tests"
