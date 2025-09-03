# tools/fix_indentation_app.py
from __future__ import annotations
import re, sys, io, os

P = os.path.join("contract_review_app","api","app.py")

def load() -> list[str]:
    with open(P, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()

def save(lines: list[str]) -> None:
    with open(P, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

def indent_block(lines: list[str], start_idx: int, end_token: str) -> None:
    """
    Зсунути на +4 пробіли всі непорожні рядки ПІСЛЯ start_idx
    до рядка, що починається з end_token на тому ж або меншому рівні.
    Використовуємо для: 'except ' ... 'finally:'  (тіло except)
    і для: 'try:' ... ('except ' | 'finally:' | перший dedent)
    """
    base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip(" "))
    i = start_idx + 1
    while i < len(lines):
        s = lines[i]
        if not s.strip():
            i += 1
            continue
        cur_indent = len(s) - len(s.lstrip(" "))
        # стоп, якщо зустріли end_token на тій самій або меншій глибині
        if s.lstrip().startswith(end_token) and cur_indent <= base_indent:
            break
        # якщо рядок має індентацію <= base_indent і не є продовженням (), \ :
        if cur_indent <= base_indent and not s.lstrip().startswith(("#",)):
            lines[i] = " " * (base_indent + 4) + s.lstrip()
        i += 1

def fix_except_finally(lines: list[str]) -> int:
    """
    Виправляє тіло 'except' у middleware cid_bodylimit_middleware:
    після 'except Exception as e:' наступні рядки мають бути індентовані до 'finally:'.
    """
    cnt = 0
    for i, s in enumerate(lines):
        if s.lstrip().startswith("except Exception as e:"):
            # якщо наступний непорожній рядок не індентований — зсунути до 'finally:'
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_indent = len(lines[j]) - len(lines[j].lstrip(" "))
                base_indent = len(s) - len(s.lstrip(" "))
                if next_indent <= base_indent:
                    indent_block(lines, i, "finally:")
                    cnt += 1
    return cnt

def fix_try_json_blocks(lines: list[str]) -> int:
    """
    Для відомих ендпойнтів вирівнює тіло після 'try:' (payload = await req.json()).
    Патерни шукаємо у функціях: /api/analyze, /api/gpt-draft, /api/suggest_edits, /api/qa-recheck.
    """
    cnt = 0
    # індекси початків функцій (приблизно; шукаємо сигнатури)
    fn_markers = [
        "async def analyze_doc",      # /api/analyze handler
        "async def gpt_draft",        # /api/gpt-draft handler
        "async def suggest_edits",    # /api/suggest_edits handler
        "async def qa_recheck",       # /api/qa-recheck handler
    ]
    # проходимо файл і виправляємо 'try:' які без тіла
    for i, s in enumerate(lines):
        if s.rstrip().endswith("try:"):
            # вважаємо, що це наш блок у згаданих функціях (безпечна евристика: в межах async def)
            # знайдемо попередній заголовок функції
            k = i
            in_target = False
            while k >= 0 and not lines[k].lstrip().startswith("async def"):
                k -= 1
            if k >= 0 and any(m in lines[k] for m in fn_markers):
                in_target = True
            if not in_target:
                continue
            # перевіряємо наступний непорожній рядок
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                base_indent = len(s) - len(s.lstrip(" "))
                next_indent = len(lines[j]) - len(lines[j].lstrip(" "))
                if next_indent <= base_indent:
                    # підняти тіло try: мінімум до +4 і до першого except/finally/dedent
                    indent_block(lines, i, "except")
                    cnt += 1
    return cnt

def detab_and_trim(lines: list[str]) -> list[str]:
    out = []
    for s in lines:
        s = s.replace("\t", "    ")
        # збережемо внутрішні пробіли; обрізаємо лише трейлінг
        s = s.rstrip()
        out.append(s)
    return out

def main():
    lines = load()
    lines = detab_and_trim(lines)
    c1 = fix_except_finally(lines)
    c2 = fix_try_json_blocks(lines)
    save(lines)
    print(f"[fix] except/finally blocks: {c1}, try-json blocks: {c2}")
    # фінальна перевірка компіляції лише цього файлу
    src = "\n".join(lines) + "\n"
    try:
        compile(src, P, "exec")
        print("[ok] compiled:", P)
    except SyntaxError as e:
        print("[fail] syntax:", e)
        sys.exit(2)

if __name__ == "__main__":
    main()
