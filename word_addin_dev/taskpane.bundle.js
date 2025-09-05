import { metaFromResponse, applyMetaToBadges, apiHealth, apiAnalyze, apiQaRecheck } from "./app/assets/api-client.js";
import { notifyOk, notifyErr } from "./app/assets/notifier.js";
import { getWholeDocText } from "./app/assets/office.js";

const Q = {
  proposed: 'textarea#proposedText, textarea[name="proposed"], textarea[data-role="proposed-text"]',
  original: 'textarea#originalClause, textarea[name="original"], textarea[data-role="original-clause"]'
};

function $(sel) {
  return document.querySelector(sel);
}

async function onGetAIDraft(ev) {
  try {
    const src = $(Q.original);
    const dst = $(Q.proposed);
    const text = (src && src.value || "").trim();
    if (!text) {
      console.info("[Draft] no source text");
      return;
    }
    const body = {
      text,
      mode: "friendly",
      before_text: "",
      after_text: ""
    };
    const resp = await fetch(`${window.__cal_base__ ?? ""}/api/gpt-draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    try { applyMetaToBadges(metaFromResponse(resp)); } catch {}
    if (!resp.ok) {
      const fail = await resp.text().catch(() => "");
      console.warn("[Draft] HTTP", resp.status, fail);
      return;
    }
    const json = await resp.json();
    const proposed = (json && json.proposed_text || "").toString();
    if (dst) {
      if (!dst.id) dst.id = "proposedText";
      if (!dst.name) dst.name = "proposed";
      dst.dataset.role = "proposed-text";
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

function bindClick(sel, fn) {
  const el = document.querySelector(sel);
  if (!el) return;
  el.addEventListener("click", (e) => { e.preventDefault(); fn(); });
  el.classList.remove("js-disable-while-busy");
}

function wireUI() {
  bindClick("#btnTest", doHealth);
  bindClick("#btnAnalyzeDoc", doAnalyzeDoc);
  bindClick("#btnQARecheck", doQARecheck);
  document.getElementById("btnGetAIDraft")?.addEventListener("click", onGetAIDraft);
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
