import { metaFromResponse, applyMetaToBadges, apiHealth, apiAnalyze, apiGptDraft, apiQaRecheck } from "./api-client";
import { notifyOk, notifyErr } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.

type Mode = "live" | "friendly" | "doctor";

async function doHealth() {
  const { json, meta } = await apiHealth();
  try { applyMetaToBadges(meta); } catch {}
  notifyOk(`Health: ${json.status} (schema ${json.schema})`);
}

async function doAnalyzeDoc() {
  const text = await getWholeDocText();
  if (!text || !text.trim()) { notifyErr("В документе нет текста"); return; }
  const { json, meta } = await apiAnalyze(text);
  try { applyMetaToBadges(meta); } catch {}
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: json }));
  notifyOk("Analyze OK");
}

async function doGptDraft() {
  const { json, meta } = await apiGptDraft("Ping draft");
  try { applyMetaToBadges(meta); } catch {}
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.draft", { detail: json }));
  notifyOk("Draft OK");
}

async function doQARecheck() {
  const text = await getWholeDocText();
  const { json, meta } = await apiQaRecheck(text, []);
  try { applyMetaToBadges(meta); } catch {}
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: json }));
  notifyOk("QA recheck OK");
}

function bindClick(sel: string, fn: () => void) {
  const el = document.querySelector(sel) as HTMLElement | null;
  if (!el) return;
  el.addEventListener("click", (e) => { e.preventDefault(); fn(); });
  el.classList.remove("js-disable-while-busy"); // чтобы точно были кликабельны
}

function wireUI() {
  bindClick("#btnTest", doHealth);
  bindClick("#btnAnalyzeDoc", doAnalyzeDoc);
  bindClick("#btnDraft", doGptDraft);            // если у вас id другой (Get AI Draft) — поправьте
  bindClick("#btnQARecheck", doQARecheck);
  // При необходимости добавьте остальные кнопки: Use selection, Insert result into Word и т.д.
  console.log("Panel UI wired");
}

async function bootstrap() {
  // 1) Ждём Office, если он есть. Если нет — ждём DOM.
  try {
    if ((window as any).Office?.onReady) {
      await (window as any).Office.onReady();
    } else {
      if (document.readyState === "loading") {
        await new Promise<void>(res => document.addEventListener("DOMContentLoaded", () => res(), { once: true }));
      }
    }
  } catch {}
  // 2) Немедленно провязываем UI
  wireUI();
  // 3) Пытаемся сразу применить мету хотя бы по /health
  try { await doHealth(); } catch {}
}

bootstrap();
