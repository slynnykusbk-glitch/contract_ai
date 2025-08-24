# tools/run_and_open_report.py
from contract_review_app.engine.pipeline import (
    discover_rules,
    run_pipeline,
    DEFAULT_RULE_MODULES,
)
from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.generate_report import generate_report


def _load_docx_paragraphs(path: str):
    from docx import Document  # python-docx

    d = Document(path)
    paras = [p.text.strip() for p in d.paragraphs if p.text and p.text.strip()]
    return [p for p in paras if len(p) >= 20][:30]  # не більше 30 для швидкості


def main():
    # беремо ваш файл
    docx_path = "contract_review_app/contract.docx"
    texts = _load_docx_paragraphs(docx_path)
    inputs = [
        AnalysisInput(clause_type="paragraph", text=t, metadata={"cli": "1"})
        for t in texts
    ]

    rules = discover_rules(DEFAULT_RULE_MODULES)
    outputs = run_pipeline(inputs, timeout_sec=2.0, rules=rules)

    out_path = "output_report.html"
    generate_report(outputs, out_path)  # відкриється, якщо CR_AUTO_OPEN=1
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
