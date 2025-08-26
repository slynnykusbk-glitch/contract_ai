from __future__ import annotations

"""Additional UK contract type patterns."""

from typing import Any, Dict

CONTRACT_TYPE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "agency": {
        "title_keywords": ["agency agreement", "agency contract"],
        "body_keywords": [
            "principal",
            "agent",
            "commission",
            "territory",
            "solicit orders",
        ],
        "boost_phrases": {"exclusive agency": 1.0},
        "negative": ["employment"],
    },
    "franchise": {
        "title_keywords": ["franchise agreement"],
        "body_keywords": [
            "franchisor",
            "franchisee",
            "royalty",
            "brand standards",
            "marketing fund",
        ],
        "boost_phrases": {"initial fee": 0.5},
    },
    "guarantee": {
        "title_keywords": ["guarantee", "deed of guarantee"],
        "body_keywords": [
            "guarantor",
            "guarantee",
            "indemnity",
            "principal debtor",
            "obligations",
        ],
        "negative": ["no guarantee"],
    },
}
