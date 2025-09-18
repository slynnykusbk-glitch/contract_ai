from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from contract_review_app.api.app import app
from contract_review_app.api.models import SCHEMA_VERSION

from tests.contract.normalizer import normalize_for_diff

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "analyze_response_v1_4.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
EXPECTED_DIR = FIXTURE_DIR / "expected"
TEST_CASES = [
    "basic",
    "governing_law",
    "payment_terms",
]


@pytest.fixture(scope="session")
def analyze_client() -> TestClient:
    os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key-123456789012345678901234")
    os.environ.setdefault("FEATURE_COMPANIES_HOUSE", "0")
    client = TestClient(app)
    yield client
    client.close()


@pytest.fixture()
def analyze_headers() -> dict[str, str]:
    return {"x-api-key": "local-test-key-123", "x-schema-version": SCHEMA_VERSION}


def _load_text(name: str) -> str:
    return (FIXTURE_DIR / f"{name}.txt").read_text()


def _load_expected(name: str) -> dict:
    return json.loads((EXPECTED_DIR / f"{name}.json").read_text())


@pytest.mark.parametrize("fixture_name", TEST_CASES)
def test_analyze_contract_contract(analyze_client: TestClient, analyze_headers: dict[str, str], fixture_name: str) -> None:
    response = analyze_client.post(
        "/api/analyze",
        json={"text": _load_text(fixture_name)},
        headers=analyze_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    VALIDATOR.validate(payload)
    normalized = normalize_for_diff(payload)
    assert normalized == _load_expected(fixture_name)


def _sample_payload() -> dict:
    summary = {
        "type": "Contract",
        "type_confidence": 0.3,
        "type_source": None,
        "doc_type": {
            "top": {"type": "Contract", "score": 0.3},
            "confidence": 0.3,
            "candidates": [{"type": "Contract", "score": 0.3}],
        },
        "parties": [
            {
                "name": "Alpha Corp",
                "role": "Supplier",
                "registry": {"number": "123", "status": "active"},
            }
        ],
        "dates": {},
        "term": {"mode": "unknown", "start": None, "end": None, "renew_notice": None},
        "governing_law": None,
        "jurisdiction": None,
        "signatures": [],
        "liability": {"has_cap": False, "cap_value": None, "cap_currency": None, "notes": None},
        "exclusivity": None,
        "currency": None,
        "carveouts": {},
        "conditions_vs_warranties": {
            "has_conditions": False,
            "has_warranties": False,
            "explicit_conditions": [],
            "explicit_warranties": [],
        },
        "hints": [],
        "rules_count": 1,
        "debug": {"doctype_top": []},
    }
    findings = [
        {
            "rule_id": "R-2",
            "severity": "low",
            "start": 5,
            "end": 15,
            "snippet": "Term",
            "citations": [
                {
                    "system": "UK",
                    "instrument": "Act",
                    "section": "1",
                    "title": "Example",
                    "source": "statute",
                },
                {
                    "system": "EU",
                    "instrument": "Directive",
                    "section": "2",
                    "title": "Another",
                    "source": "eu",
                },
            ],
        },
        {
            "rule_id": "R-1",
            "severity": "high",
            "start": 20,
            "end": 30,
            "normalized_snippet": "payment",
            "citations": [
                {
                    "system": "UK",
                    "instrument": "Act",
                    "section": "3",
                    "title": "Supplement",
                    "source": "statute",
                }
            ],
        },
    ]
    meta = {
        "provider": "mock",
        "model": "static",
        "valid_config": True,
        "document_type": "Contract",
        "language": "en-GB",
        "text_bytes": 120,
        "active_packs": ["beta", "alpha"],
        "rules_loaded_count": 2,
        "rules_fired_count": 2,
        "rules_evaluated": 2,
        "fired_rules": [
            {
                "rule_id": "R-2",
                "name": "Rule two",
                "pack": "pack-b",
                "positions": [{"start": 5, "end": 15}],
                "requires_clause_hit": False,
            },
            {
                "rule_id": "R-1",
                "pack": "pack-a",
                "positions": [{"start": 20, "end": 30}],
                "requires_clause_hit": True,
            },
        ],
        "pipeline_id": "abc123",
        "timings_ms": {"parse_ms": 1.2},
        "debug": {"pipeline": "abc123", "packs": ["alpha"], "rules_loaded": 2, "rules_evaluated": 2, "rules_triggered": 2},
    }
    payload = {
        "status": "ok",
        "analysis": {"status": "ok", "findings": deepcopy(findings)},
        "results": {"summary": deepcopy(summary)},
        "clauses": deepcopy(findings),
        "document": {},
        "schema_version": "1.4",
        "meta": meta,
        "summary": deepcopy(summary),
        "cid": "cid-1",
        "findings": deepcopy(findings),
        "recommendations": [],
        "rules_coverage": {
            "doc_type": {"value": "contract", "source": "heuristic"},
            "rules": [
                {"rule_id": "R-1", "status": "matched"},
                {"rule_id": "R-2", "status": "missed"},
            ],
        },
    }
    return payload


def test_normalizer_idempotent() -> None:
    payload = _sample_payload()
    first = normalize_for_diff(payload)
    second = normalize_for_diff(first)
    assert first == second
    parties = first["summary"]["parties"]
    assert parties == [{"name": "Alpha Corp", "role": "Supplier"}]


def test_normalizer_permutation_invariance() -> None:
    payload = _sample_payload()
    permuted = _sample_payload()
    permuted["findings"].reverse()
    permuted["analysis"]["findings"].reverse()
    permuted["clauses"].reverse()
    permuted["meta"]["active_packs"].reverse()
    permuted["meta"]["fired_rules"].reverse()
    permuted["rules_coverage"]["rules"].reverse()
    for finding in permuted["findings"]:
        if "citations" in finding:
            finding["citations"].reverse()
    assert normalize_for_diff(payload) == normalize_for_diff(permuted)
