import { metaFromResponse, applyMetaToBadges } from "./api-client";
import { notifyOk, notifyErr } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.

type Mode = "live" | "friendly" | "doctor";

function backendBase(): string {
  const inp = document.getElementById("backendUrl") as HTMLInputElement | null;
  return inp?.value?.trim() || "https://localhost:9443";
}

async function safeFetch(input: RequestInfo, init?: RequestInit): Promise<Response> {
  const resp = await fetch(input, init);
  // даже если тело 4xx/5xx — мету применяем: так заполнятся бейджи (cid/schema/provider/…)
  try { applyMetaToBadges( metaFromResponse(resp) ); } catch {}
  return resp;
}

async function doHealth() {
  const r = await safeFetch(`${backendBase()}/health`);
  const j = await r.json();
  notifyOk(`Health: ${j.status} (schema ${j.schema})`);
}

async function doAnalyzeDoc() {
  const text = await getWholeDocText();
  if (!text || !text.trim()) { notifyErr("В документе нет текста"); return; }
  const r = await safeFetch(`${backendBase()}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, mode: "live" })
  });
  const j = await r.json();
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.results", { detail: j }));
  notifyOk("Analyze OK");
}

async function doGptDraft() {
  const r = await safeFetch(`${backendBase()}/api/gpt-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: "Ping draft", mode: "friendly", before_text: "", after_text: "" })
  });
  const j = await r.json();
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.draft", { detail: j }));
  notifyOk("Draft OK");
}

async function doQARecheck() {
  // Пустые rules разрешены, бекенд их нормализует (последний PR)
  const r = await safeFetch(`${backendBase()}/api/qa-recheck`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: await getWholeDocText(), rules: [] })
  });
  const j = await r.json();
  (document.getElementById("results") || document.body).dispatchEvent(new CustomEvent("ca.qa", { detail: j }));
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
