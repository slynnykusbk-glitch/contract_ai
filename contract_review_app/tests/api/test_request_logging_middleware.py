import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

os.environ.setdefault("AZURE_OPENAI_API_KEY", "test")
os.environ.setdefault("SCHEMA_VERSION", "1.4")

from contract_review_app.api.app import app  # noqa: E402
from contract_review_app.api.models import SCHEMA_VERSION  # noqa: E402

client = TestClient(app)
HEADERS = {"x-api-key": "k", "x-schema-version": SCHEMA_VERSION}


def test_request_logging_middleware_logs():
    mock_logger = Mock()
    parsed = SimpleNamespace(segments=[])
    with (
        patch("contract_review_app.api.app.cai_logger", mock_logger),
        patch("contract_review_app.legal_rules.loader.load_rule_packs"),
        patch("contract_review_app.legal_rules.loader.filter_rules", return_value=[]),
        patch("contract_review_app.legal_rules.engine.analyze", return_value=[]),
        patch(
            "contract_review_app.api.app.analysis_parser.parse_text",
            return_value=parsed,
        ),
        patch("contract_review_app.api.app.analysis_classifier.classify_segments"),
        patch(
            "contract_review_app.api.app._discover_rules_count",
            new=AsyncMock(return_value=0),
        ),
    ):
        resp = client.post("/api/analyze", json={"text": "hi"}, headers=HEADERS)
    assert resp.status_code == 200
    assert mock_logger.info.called
    args, kwargs = mock_logger.info.call_args
    assert kwargs["method"] == "POST"
    assert kwargs["path"] == "/api/analyze"
    assert kwargs["status"] == resp.status_code
    assert "ms" in kwargs
