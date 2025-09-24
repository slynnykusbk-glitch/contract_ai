import os

# 📌 Коренева папка, в якій шукати Python-файли
BASE_DIR = os.path.join(os.path.dirname(__file__), "rules")

# ❌ Імпорт-шаблони, які потрібно видалити
INVALID_PATTERNS = ["utils", "helpers", "utils_patterns", "utils_citations"]


def is_invalid_import(line: str) -> bool:
    line = line.strip()
    return (line.startswith("from") or line.startswith("import")) and any(
        p in line for p in INVALID_PATTERNS
    )


def clean_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = []
    removed = []

    for line in lines:
        if is_invalid_import(line):
            removed.append(line.strip())
        else:
            cleaned_lines.append(line)

    if removed:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)
        print(f"✅ Cleaned: {filepath}")
        for r in removed:
            print(f"   ⛔ Removed: {r}")


def process_all_py_files():
    found = False
    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith(".py"):
                found = True
                filepath = os.path.join(root, file)
                clean_file(filepath)

    if not found:
        print(f"⚠️ No .py files found in {BASE_DIR}. Check path!")


if __name__ == "__main__":
    process_all_py_files()
