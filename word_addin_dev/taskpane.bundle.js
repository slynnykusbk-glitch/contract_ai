import { metaFromResponse, applyMetaToBadges, apiHealth, apiAnalyze, apiGptDraft, apiQaRecheck } from "./app/assets/api-client.js";
import { notifyOk, notifyErr } from "./app/assets/notifier.js";
import { getWholeDocText } from "./app/assets/office.js";

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

function bindClick(sel, fn) {
  const el = document.querySelector(sel);
  if (!el) return;
  el.addEventListener("click", (e) => { e.preventDefault(); fn(); });
  el.classList.remove("js-disable-while-busy");
}

function wireUI() {
  bindClick("#btnTest", doHealth);
  bindClick("#btnAnalyzeDoc", doAnalyzeDoc);
  bindClick("#btnDraft", doGptDraft);
  bindClick("#btnQARecheck", doQARecheck);
  console.log("Panel UI wired");
}

async function bootstrap() {
  try {
    if (window.Office?.onReady) {
      await window.Office.onReady();
    } else {
      if (document.readyState === "loading") {
        await new Promise(res => document.addEventListener("DOMContentLoaded", () => res(), { once: true }));
      }
    }
  } catch {}
  wireUI();
  try { await doHealth(); } catch {}
}

bootstrap();
