from pathlib import Path


def pytest_ignore_collect(path, config):
    p = Path(str(path))
    parts = [s.lower() for s in p.parts]
    if "contract_review_app" in parts:
        idx = parts.index("contract_review_app")
        tail = parts[idx + 1 :]
        if tail and tail[0] != "tests" and p.name.lower().startswith(("test_",)):
            return True
    return False
