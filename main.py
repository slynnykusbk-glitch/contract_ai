from __future__ import annotations

"""Demo entry point for Contract AI rule analysis."""

import os
import sys

from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.generate_report import generate_report
from contract_review_app.legal_rules.legal_rules import analyze as run_rule
from contract_review_app.legal_rules.registry import RULES_REGISTRY
from contract_review_app.utils.logging import init_logging

# спробуємо взяти зручний лоадер DOCX, якщо є
try:
    from contract_review_app.core.load_docx_text import load_docx_text
except Exception:
    load_docx_text = None  # впадемо на fallback

logger = init_logging()

DEMO_TEXT = """\
THIS SAMPLE CONTRACT (demo) — minimal text to let rules run.
Termination: either party may terminate for material breach with 30 days' written notice and a cure period.
Confidentiality: each Party shall keep Confidential Information secret; carve-outs include information required by law.
Governing law: laws of England and Wales. Jurisdiction: courts of England have exclusive jurisdiction.
Force Majeure: epidemic, war, governmental order; notice within 10 days; reasonable efforts to mitigate; terminate after 90 days.
Indemnity: Supplier shall indemnify Customer against losses, claims, costs and expenses; subject to the limitation of liability set out herein.
"""


def load_contract_text() -> str:
    """
    1) ./sample_contract.docx
    2) ./sample_contract.txt
    3) DEMO_TEXT (вшитий)
    """
    docx_path = os.path.abspath("sample_contract.docx")
    txt_path = os.path.abspath("sample_contract.txt")

    # DOCX
    if load_docx_text and os.path.exists(docx_path):
        try:
            logger.info("📄 Loading DOCX: {}", docx_path)
            return load_docx_text(docx_path)
        except Exception as e:
            logger.warning("⚠ DOCX loader failed: {}", e)

    # TXT
    if os.path.exists(txt_path):
        try:
            logger.info("📄 Loading TXT: {}", txt_path)
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning("⚠ TXT loader failed: {}", e)

    logger.warning("⚠ sample_contract.* not found — using built-in demo text.")
    return DEMO_TEXT


def main():
    print("📦 RULES_REGISTRY contains:", list(RULES_REGISTRY.keys()))
    contract_text = load_contract_text()

    # Готуємо інпути для ВСІХ правил бізнес-рівня (усі ключі з реєстру)
    inputs = [
        AnalysisInput(
            clause_type=rule_name, text=contract_text, metadata={"name": rule_name}
        )
        for rule_name in RULES_REGISTRY.keys()
    ]

    # Проганяємо кожне правило через центральний диспетчер
    results = []
    print("🔍 Running analysis for", len(inputs), "clauses...")
    for inp in inputs:
        try:
            out = run_rule(inp)  # legal_rules.legal_rules.analyze
            results.append(out)
            print(
                f"  ✔ {inp.clause_type}: {out.status} (score={getattr(out, 'score', '?')})"
            )
        except Exception:
            # Безпечно фіксуємо збій одного правила, щоб інші не постраждали
            logger.exception("Rule '{rule}' crashed; continuing…", rule=inp.clause_type)

    # Генеруємо звіт
    out_file = os.path.abspath("report.html")
    try:
        generate_report(results, output_file=out_file)  # УВАГА: тут саме output_file
        print(f"✅ Report generated: {out_file}")
        # Для Windows можна одразу відкрити в браузері:
        try:
            import webbrowser

            webbrowser.open(f"file:///{out_file}")
        except Exception:
            pass
    except TypeError as e:
        # Підказка якщо знову сплутаємо параметр
        if "output_path" in str(e):
            print(
                "❌ generate_report() не приймає 'output_path'. Використай 'output_file'."
            )
        raise


if __name__ == "__main__":
    # Додамо корінь проєкту в PYTHONPATH на випадок запуску поза venv
    sys.path.append(os.path.abspath("."))
    main()
