# contract_review_app/tools/make_report.py
from contract_review_app.engine.pipeline import (
    discover_rules,
    run_pipeline,
    DEFAULT_RULE_MODULES,
)
from contract_review_app.core.schemas import AnalysisInput
from contract_review_app.generate_report import generate_report


def main():
    text = (
        "This Agreement shall be governed by and construed in accordance with the laws of "
        "England and Wales, excluding its conflict of laws rules."
    )
    inputs = [AnalysisInput(clause_type="paragraph", text=text, metadata={"demo": "1"})]

    print(f"[diag] inputs: {len(inputs)} items")
    rules = discover_rules(DEFAULT_RULE_MODULES)
    print(f"[diag] rules discovered: {list(rules.keys())}")

    outs = run_pipeline(inputs, timeout_sec=2.0, rules=rules)
    print(f"[diag] outputs: {len(outs)} items")
    if outs:
        print("[diag] sample:", outs[0].diagnostics.get("rule"), outs[0].status)

    out_path = "contract_review_app/NEW_output_report.html"
    generate_report(outs, out_path)
    print("[diag] wrote:", out_path)


if __name__ == "__main__":
    main()
