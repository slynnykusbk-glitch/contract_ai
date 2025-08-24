# tools/bundle_merger.py
from __future__ import annotations
import argparse
import json
import shutil
import zipfile
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / ".imports"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def unzip(zip_path: Path, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(target)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--zip", required=True, help="Шлях до contract_review_app_refined.zip"
    )
    ap.add_argument(
        "--apply", action="store_true", help="Застосувати зміни (інакше — dry-run)"
    )
    args = ap.parse_args()

    zip_path = Path(args.zip).resolve()
    tmp_dir = IMPORTS / "incoming"
    conflicts_dir = IMPORTS / "conflicts"
    report_path = IMPORTS / "merge_report.json"
    plan_path = IMPORTS / "keep_plan.json"

    # очистка робочих тек
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    if conflicts_dir.exists():
        shutil.rmtree(conflicts_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    conflicts_dir.mkdir(parents=True, exist_ok=True)
    IMPORTS.mkdir(parents=True, exist_ok=True)

    # розпакувати
    unzip(zip_path, tmp_dir)

    # корінь у ZIP має містити contract_review_app/
    incoming_root = tmp_dir / "contract_review_app"
    if not incoming_root.exists():
        raise SystemExit("У архіві немає директорії contract_review_app/")

    # файли, які НЕ можна перезаписати
    protect = {
        "contract_review_app/legal_rules/governing_law.py",
        "contract_review_app/legal_rules/base.py",
    }

    summary = {
        "added": [],
        "identical": [],
        "conflicts": [],
        "protected_skipped": [],
        "updated": [],
    }

    for src in incoming_root.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(tmp_dir).as_posix()  # includes contract_review_app/...
        dst = ROOT / rel

        # Захист
        if rel in protect and dst.exists():
            summary["protected_skipped"].append(rel)
            continue

        if not dst.exists():
            if args.apply:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            summary["added"].append(rel)
            continue

        # є файл і тут, і там: порівнюємо
        if sha256(src) == sha256(dst):
            summary["identical"].append(rel)
            continue

        # різні — конфлікт
        conf_ours = conflicts_dir / (rel.replace("/", "__") + ".ours")
        conf_theirs = conflicts_dir / (rel.replace("/", "__") + ".theirs")
        conf_ours.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, conf_ours)
        shutil.copy2(src, conf_theirs)
        summary["conflicts"].append(rel)

    # збережемо звіт
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # початковий keep-plan
    keep_plan = {rel: "ours" for rel in summary["conflicts"]}
    with plan_path.open("w", encoding="utf-8") as f:
        json.dump(keep_plan, f, ensure_ascii=False, indent=2)

    print("[INFO] Dry-run report saved to:", report_path)
    print("[INFO] Conflicts plan saved to:", plan_path)
    if args.apply:
        print("[INFO] Changes applied where no conflicts/protected files.")
    else:
        print("[INFO] No changes applied (dry-run). Use --apply to write.")


if __name__ == "__main__":
    main()
