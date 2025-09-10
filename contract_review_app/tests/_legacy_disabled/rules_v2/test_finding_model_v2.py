from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[3]))

from datetime import datetime, UTC

import pytest
from pydantic import ValidationError

from contract_review_app.rules_v2 import ENGINE_VERSION, FindingV2


def build_valid_finding() -> FindingV2:
    return FindingV2(
        id="1",
        pack="pk",
        rule_id="r1",
        title={"en": "Title"},
        severity="High",
        category="cat",
        message={"en": "msg"},
        explain={"en": "exp"},
        suggestion={"en": "sug"},
        version="0",
        created_at=datetime.now(UTC),
        engine_version=ENGINE_VERSION,
    )


def test_valid_finding_model() -> None:
    finding = build_valid_finding()
    assert finding.severity == "High"
    assert finding.title["en"] == "Title"


def test_severity_constraint() -> None:
    with pytest.raises(ValidationError):
        FindingV2(
            id="1",
            pack="pk",
            rule_id="r1",
            title={"en": "t"},
            severity="critical",  # type: ignore[arg-type]
            category="cat",
            message={"en": "m"},
            explain={"en": "e"},
            suggestion={"en": "s"},
            version="0",
            created_at=datetime.now(UTC),
            engine_version=ENGINE_VERSION,
        )


def test_en_required() -> None:
    with pytest.raises(ValidationError):
        FindingV2(
            id="1",
            pack="pk",
            rule_id="r1",
            title={"uk": "t"},
            severity="Low",
            category="cat",
            message={"en": "m"},
            explain={"en": "e"},
            suggestion={"en": "s"},
            version="0",
            created_at=datetime.now(UTC),
            engine_version=ENGINE_VERSION,
        )
