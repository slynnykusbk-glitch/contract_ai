import os
import re

RULES_DIR = "contract_review_app/legal_rules/rules"


def check_rule_return_types():
    flagged_files = []

    for root, _, files in os.walk(RULES_DIR):
        for file in files:
            if file.endswith(".py") and not file.startswith("test_"):
                full_path = os.path.join(root, file)
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Find analyze() function
                if "def analyze(" in content:
                    # Look for 'return {' inside analyze()
                    analyze_start = content.find("def analyze(")
                    analyze_block = content[analyze_start:]
                    return_dict_match = re.search(r"\breturn\s+{", analyze_block)

                    if return_dict_match:
                        flagged_files.append((file, return_dict_match.group()))

    print("🔎 Rule Check Results:")
    if not flagged_files:
        print("✅ All rule functions return AnalysisOutput properly.")
    else:
        print(
            "⚠️ The following rule files may return a dict instead of AnalysisOutput:\n"
        )
        for filename, line in flagged_files:
            print(f"📄 {filename}: {line}")


if __name__ == "__main__":
    check_rule_return_types()
