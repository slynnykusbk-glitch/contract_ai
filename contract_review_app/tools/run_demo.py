import os
import logging
import re
from typing import Dict

from document_checker import extract_clauses_flexible
from generate_report import generate_report
from load_docx_text import load_docx_text
from legal_rules import validate_clause, cross_check_clauses

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SAMPLE_CONTRACT = """
THIS AGREEMENT is made between Alpha Ltd (the "Client"), incorporated in England,
and Beta LLP (the "Contractor"), registered in Scotland, each acting through its duly authorised officer.

1. DEFINITIONS AND INTERPRETATION
"Agreement" means this services contract between the Parties.
"Services" means the consulting services to be performed by the Contractor.
"Deliverables" means the outputs to be provided and accepted in accordance with the Schedule.
"Effective Date" means 01 August 2025.
"Term" means the period from the Effective Date until termination under clause 10.
Personal Data shall have the meaning given in the UK GDPR. Each Party shall comply with applicable data protection laws.
Each Party represents compliance with the Bribery Act 2010.

2. GOVERNING LAW
This Agreement shall be governed by the laws of England.

3. CONFIDENTIALITY
The Parties shall keep Confidential Information secret and use it only for the purpose of the Agreement.

10. TERMINATION
Either Party may terminate on 30 days’ notice for convenience.
"""


def _fallback_extract_clauses(text: str) -> Dict[str, Dict[str, str]]:
    """
    Якщо з якоїсь причини extract_clauses_flexible не поверне потрібну клаузулу,
    виділяємо мінімально необхідні вручну для інтеграційного тесту.
    """
    clauses: Dict[str, Dict[str, str]] = {}

    # Parties & Definitions (шукаємо секцію з Definitions/Interpretation)
    m = re.search(
        r"(?:^|\n)\s*1\.\s*(definitions|interpretation).*?(?=\n\d+\.\s|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        clauses["parties and definitions"] = {
            "text": m.group(0),
            "category": "core_legal",
        }
    else:
        # Якщо немає окремого блоку, візьмемо преамбулу + абзац після
        preamble = text[: min(800, len(text))]
        clauses["parties and definitions"] = {
            "text": preamble,
            "category": "core_legal",
        }

    # Governing law
    g = re.search(
        r"(?:^|\n)\s*\d+\.\s*governing law.*?(?=\n\d+\.\s|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if g:
        clauses["governing law"] = {"text": g.group(0), "category": "core_legal"}

    # Confidentiality
    c = re.search(
        r"(?:^|\n)\s*\d+\.\s*confidential.*?(?=\n\d+\.\s|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if c:
        clauses["confidentiality"] = {"text": c.group(0), "category": "core_legal"}

    # Termination
    t = re.search(
        r"(?:^|\n)\s*\d+\.\s*termination.*?(?=\n\d+\.\s|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if t:
        clauses["termination"] = {"text": t.group(0), "category": "core_legal"}

    return clauses


def run_analysis():
    contract_path = "contract.docx"
    if os.path.exists(contract_path):
        logger.info(f"📄 Using DOCX: {contract_path}")
        text = load_docx_text(contract_path)
        if not text:
            logger.warning(
                "⚠️ Empty contract text in DOCX. Falling back to sample text."
            )
            text = SAMPLE_CONTRACT
    else:
        logger.info(
            "ℹ️ contract.docx not found. Using built-in SAMPLE_CONTRACT for end-to-end test."
        )
        text = SAMPLE_CONTRACT

    # 1️⃣ Extract clauses
    try:
        clauses_raw = extract_clauses_flexible(text)
        if (
            not isinstance(clauses_raw, dict)
            or "parties and definitions" not in clauses_raw
        ):
            logger.warning(
                "⚠️ Extractor did not return expected structure or missing 'parties and definitions'. Using fallback."
            )
            clauses_raw = _fallback_extract_clauses(text)
    except Exception as e:
        logger.error(f"Extractor failed: {e}. Using fallback.")
        clauses_raw = _fallback_extract_clauses(text)

    # 2️⃣ Validate clauses
    clause_results: Dict[str, Dict] = {}
    for clause_name, clause_data in clauses_raw.items():
        clause_text = clause_data.get("text", "")
        category = clause_data.get("category", "unknown")

        try:
            validated = validate_clause(clause_name, clause_text)
        except Exception as e:
            logger.exception(f"Validation crashed for '{clause_name}': {e}")
            validated = {
                "status": "❌",
                "score": 0,
                "risk_level": "high",
                "severity": "high",
                "issue_type": "validation_exception",
                "problem": str(e),
                "recommendation": "Fix exception in rule engine.",
                "law_reference": "",
                "category": category,
                "text": clause_text,
                "keywords": [],
            }

        if isinstance(validated, dict):
            # Переконаємось, що обов’язкові поля не None
            for k in [
                "status",
                "score",
                "risk_level",
                "severity",
                "issue_type",
                "problem",
                "recommendation",
                "law_reference",
                "category",
                "text",
                "keywords",
            ]:
                validated.setdefault(k, "" if k not in {"score"} else 0)
            validated["text"] = clause_text
            validated["category"] = category
            clause_results[clause_name] = validated
        else:
            clause_results[clause_name] = {
                "text": clause_text,
                "category": category,
                "status": "❌",
                "score": 0,
                "risk_level": "high",
                "severity": "high",
                "issue_type": "invalid_return",
                "problem": "validate_clause returned non-dict.",
                "recommendation": "Ensure validators return a dict.",
                "law_reference": "",
                "keywords": [],
            }

    # 3️⃣ Cross-check
    try:
        cross_issues = cross_check_clauses(clause_results)
        if cross_issues:
            clause_results["🧠 Clause Cross-check"] = {
                "text": "",
                "category": "meta",
                "status": "⚠️",
                "score": 0,
                "risk_level": "low",
                "severity": "low",
                "issue_type": "cross_check_findings",
                "problem": "; ".join(cross_issues),
                "recommendation": "Review cross-clause logic for conflicts or gaps.",
                "law_reference": "",
                "keywords": [],
            }
    except Exception as e:
        logger.exception(f"Cross-check failed: {e}")

    # 4️⃣ Generate report
    output_path = "output_report.html"
    generate_report(clause_results=clause_results, output_path=output_path)
    logger.info(f"✅ Report generated at: {output_path}")

    # 5️⃣ Console summary
    logger.info("— Summary —")
    for name, res in clause_results.items():
        logger.info(
            f"{name}: {res.get('status')} | {res.get('issue_type')} | score={res.get('score')}"
        )


if __name__ == "__main__":
    run_analysis()
