import os

def fix_indents_in_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed_lines = [line.replace("\t", "    ") for line in lines]  # табуляція → 4 пробіли
    if lines == fixed_lines:
        return False  # нічого не змінено

    # створимо резервну копію
    backup_path = filepath + ".bak"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # зберігаємо виправлену версію
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(fixed_lines)

    return True

def run_on_legal_rules_folder():
    base_path = os.path.join("contract_review_app", "legal_rules")
    fixed_files = []

    for root, _, files in os.walk(base_path):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                if fix_indents_in_file(full_path):
                    fixed_files.append(full_path)

    if fixed_files:
        print("✅ Fixed files:")
        for f in fixed_files:
            print(" -", f)
    else:
        print("✅ No files needed fixing.")

if __name__ == "__main__":
    run_on_legal_rules_folder()
