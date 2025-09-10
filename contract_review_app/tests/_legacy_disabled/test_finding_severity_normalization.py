import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from contract_review_app.core.schemas import Finding


def test_severity_level_synonyms():
    cases = [
        ("information", "info"),
        ("Low", "minor"),
        ("MED", "major"),
        ("moderate", "major"),
        ("High", "critical"),
        ("severe", "critical"),
        ("unexpected", "major"),
    ]
    for given, expected in cases:
        f = Finding(code="X", message="m", severity=given)
        assert f.severity_level == expected


def test_severity_level_none():
    f = Finding(code="X", message="m")
    assert f.severity_level is None
