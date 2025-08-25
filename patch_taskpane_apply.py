# patch_taskpane_apply.py
import sys, re, time, pathlib

NEW_FUNC = r'''
function applyDraftTracked(){
  var t = val(els.draft);
  if (!t) { status("Nothing to apply."); return; }
  if (!window.Word || !Word.run) { status("⚠️ Word API not available"); return; }

  Word.run(function(ctx){
    try {
      if (ctx.document && ctx.document.changeTrackingMode) {
        ctx.document.changeTrackingMode = Word.ChangeTrackingMode.trackAll;
      }
    } catch (_) {}

    var sel = ctx.document.getSelection();
    sel.load("text");

    return ctx.sync().then(function(){
      // 1) Якщо є виділення — вставляємо туди
      if (sel && typeof sel.text === "string" && sel.text.length > 0) {
        sel.insertText(t, "Replace");
        try { sel.insertComment("Contract Assistant — applied draft"); } catch(_){}
        return ctx.sync();
      }

      // 2) Беремо обрану клаузу з дропдауна
      var dd = document.getElementById("cai-clause-select");
      var clauseId = dd && dd.value ? dd.value : null;
      if (!clauseId) {
        sel.insertText(t, "Replace");
        try { sel.insertComment("Contract Assistant — applied draft"); } catch(_){}
        return ctx.sync();
      }

      // 3) Контент-контрол за clauseId
      var S = window.CAI_STATE || {};
      var map = (S.clauseMap && S.clauseMap[clauseId]) ? S.clauseMap[clauseId] : null;

      if (map && map.ccId) {
        var ccs = ctx.document.contentControls.getById(map.ccId);
        ccs.load("items");
        return ctx.sync().then(function(){
          var rng = (ccs.items && ccs.items.length) ? ccs.items[0].getRange() : sel;
          rng.insertText(t, "Replace");
          try { rng.insertComment("Contract Assistant — applied draft"); } catch(_){}
          return ctx.sync();
        });
      }

      // 4) Пошук по якорю заголовка
      var head = map && map.anchors ? (map.anchors.head || "") : "";
      if (head && head.length >= 6) {
        var found = ctx.document.body.search(head, { matchCase:false, matchWholeWord:false, ignorePunct:true, ignoreSpace:true });
        found.load("items");
        return ctx.sync().then(function(){
          var rng = (found.items && found.items.length) ? found.items[0] : sel;
          rng.insertText(t, "Replace");
          try { rng.insertComment("Contract Assistant — applied draft"); } catch(_){}
          return ctx.sync();
        });
      }

      // 5) Фінальний fallback — у поточне місце курсора
      sel.insertText(t, "Replace");
      try { sel.insertComment("Contract Assistant — applied draft"); } catch(_){}
      return ctx.sync();
    });
  })
  .then(function(){ status("Applied as tracked changes."); enableApply(true); })
  .catch(function(err){ status("❌ Apply failed: " + (err && err.message ? err.message : err)); });
}
'''.strip() + "\n"

def find_func_bounds(src: str, name: str):
    """Пошук початку 'function name(...) {' та відповідної закриваючої '}' з урахуванням рядків/коментарів."""
    start = src.find(f"function {name}(")
    if start < 0:
        return None
    # знайти першу '{' після сигнатури
    brace = src.find("{", start)
    if brace < 0:
        return None
    i = brace
    n = len(src)
    depth = 0
    in_s, s_ch = False, ""
    in_sl_comment = False
    in_ml_comment = False
    while i < n:
        ch = src[i]
        ch2 = src[i:i+2]
        # завершення коментарів
        if in_sl_comment:
            if ch == "\n":
                in_sl_comment = False
            i += 1
            continue
        if in_ml_comment:
            if ch2 == "*/":
                in_ml_comment = False
                i += 2
            else:
                i += 1
            continue
        # початок коментарів
        if not in_s and ch2 == "//":
            in_sl_comment = True
            i += 2
            continue
        if not in_s and ch2 == "/*":
            in_ml_comment = True
            i += 2
            continue
        # рядки
        if not in_s and ch in ("'", '"', "`"):
            in_s = True
            s_ch = ch
            i += 1
            continue
        if in_s:
            if ch == "\\":
                i += 2
                continue
            if ch == s_ch:
                in_s = False
            i += 1
            continue
        # підрахунок дужок
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                return start, end
        i += 1
    return None

def patch_file(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    bounds = find_func_bounds(text, "applyDraftTracked")
    if not bounds:
        print("❌ Не знайдено function applyDraftTracked() у файлі:", path)
        sys.exit(2)
    s, e = bounds
    before = text[:s]
    after  = text[e:]
    # Вставляємо нову функцію з тим же відступом, що й оригінал
    indent = re.match(r'[ \t]*', text[s:]).group(0)
    new_block = ("\n" + indent + NEW_FUNC.replace("\n", "\n"+indent)).rstrip() + "\n"
    out = before + new_block + after
    backup = path.with_suffix(path.suffix + f".bak-{int(time.time())}")
    backup.write_text(text, encoding="utf-8")
    path.write_text(out, encoding="utf-8")
    print(f"✅ Patched applyDraftTracked() in {path}\n📦 Backup: {backup}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python patch_taskpane_apply.py <path-to-taskpane.bundle.js>")
        sys.exit(1)
    patch_file(pathlib.Path(sys.argv[1]))
