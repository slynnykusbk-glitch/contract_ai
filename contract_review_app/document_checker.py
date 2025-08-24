# contract_review_app/document_checker.py

import logging
from typing import Dict

from contract_review_app.core.schemas import AnalysisInput, AnalysisOutput
from contract_review_app.legal_rules import legal_rules
from contract_review_app.config import CLAUSE_KEYWORDS

logging.basicConfig(level=logging.INFO)

def extract_clauses_flexible(text: str) -> Dict[str, dict]:
    """
    Searches for clause blocks using clause keywords.
    Returns dictionary of {clause_type: {"text": clause_text, "name": ..., "category": ...}}.
    """
    result = {}
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    paragraphs_lower = [p.lower() for p in paragraphs]

    for clause_type, keywords in CLAUSE_KEYWORDS.items():
        for idx, para in enumerate(paragraphs_lower):
            if any(keyword in para for keyword in keywords):
                start = max(0, idx - 1)
                end = min(len(paragraphs), idx + 2)
                result[clause_type] = {
                    "text": "\n\n".join(paragraphs[start:end]),
                    "category": "core",
                    "name": clause_type
                }
                break

    return result


def analyze_document(text: str) -> dict:
    print("🔍 analyze_document: Start")

    clauses = extract_clauses_flexible(text)
    print(f"🔍 Clauses extracted: {list(clauses.keys())}")

    # ✅ Новий діагностичний блок:
    from contract_review_app.legal_rules.registry import RULES_REGISTRY
    print(f"📦 RULES_REGISTRY contains: {list(RULES_REGISTRY.keys())}")

    results = {}

    for clause_type, info in clauses.items():
        print(f"⚙️ Analyzing: {clause_type}")

        input_data = AnalysisInput(
            clause_type=clause_type,
            text=info["text"],
            metadata={
                "category": info.get("category", ""),
                "name": info.get("name", "")
            }
        )

        output: AnalysisOutput = legal_rules.analyze(input_data)
        results[clause_type] = output

        # 🔁 Серіалізація у звичайний словник (JSON-compatible)
    serialized_results = {
        clause_type: output.dict() for clause_type, output in results.items()
    }

    print("✅ analyze_document: Done")

    return {
        "document_name": "contract.docx",
        "results": serialized_results
    }

