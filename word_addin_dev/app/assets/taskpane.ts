import { metaFromResponse, applyMetaToBadges, apiHealth, apiAnalyze, apiQaRecheck } from "./api-client";
import { notifyOk, notifyErr } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.

type Mode = "live" | "friendly" | "doctor";

const Q = {
  proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
};

function $(sel: string): HTMLTextAreaElement | null {
  return document.querySelector(sel) as HTMLTextAreaElement | null;
}

async function onGetAIDraft(ev?: Event) {
  try {
    const src = $(Q.original);
    const dst = $(Q.proposed);

    const text = (src?.value ?? "").trim();
    if (!text) {
      console.info("[Draft] no source text");
      return;
    }

    const body = {
      text,
      mode: "friendly",
      before_text: "",   // Word selection context not wired yet
      after_text: ""
    };

    const resp = await fetch(`${(window as any).__cal_base__ ?? ""}/api/gpt-draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    // Обновим бейджи из заголовков
    try { applyMetaToBadges(metaFromResponse(resp)); } catch {}

    if (!resp.ok) {
      const fail = await resp.text().catch(() => "");
      console.warn("[Draft] HTTP", resp.status, fail);
      return;
    }

    const json = await resp.json();
    const proposed = (json?.proposed_text ?? "").toString();

    if (dst) {
      // стабилизируем селекторы и наполняем
      if (!dst.id) dst.id = "proposedText";
      if (!dst.name) dst.name = "proposed";
      (dst as any).dataset.role = "proposed-text";

      dst.value = proposed;
      dst.dispatchEvent(new Event("input", { bubbles: true }));
      console.info("[Draft] proposed filled");
    } else {
      console.warn("[Draft] proposed textarea not found");
    }
  } catch (e) {
    console.error("[Draft] error", e);
  }
}

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
  bindClick("#btnQARecheck", doQARecheck);
  document.getElementById("btnGetAIDraft")?.addEventListener("click", onGetAIDraft);
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
