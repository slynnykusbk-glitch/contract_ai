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

(function () {
  function findProposedTextarea() {
    var el = document.querySelector('#proposedText, textarea[name="proposed"], [data-role="proposed-text"]');
    if (el) return el;
    var all = Array.prototype.slice.call(document.querySelectorAll('textarea'));
    for (var i = 0; i < all.length; i++) {
      var t = all[i];
      var around = (t.getAttribute('placeholder') || '') + ' ' +
        (t.id || '') + ' ' + (t.name || '') + ' ' +
        ((t.closest && t.closest('.card, .form-group, section') || {}).textContent || '');
      if (/proposed|suggest(ed)? edits|draft/i.test(around)) return t;
    }
    return null;
  }
  function injectProposedText(text) {
    var target = findProposedTextarea();
    if (!target) { window.toast && window.toast('Draft created, but target field not found', 'warn'); return; }
    target.value = text || '';
    target.dispatchEvent(new Event('input', { bubbles: true }));
  }
  async function onGetAIDraft(ev) {
    ev && ev.preventDefault && ev.preventDefault();
    var origEl = document.getElementById('originalClause');
    var original = (origEl && origEl.value || '').trim();
    var body = { text: original || 'Please propose a neutral confidentiality clause.', mode: 'friendly', before_text: '', after_text: '' };
    var resp = await fetch('/api/gpt-draft', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    try {
      var mod = await import('./app/assets/api-client.js');
      mod.applyMetaToBadges(mod.metaFromResponse(resp));
    } catch (e) {}
    var json = await resp.json();
    window.__last = window.__last || {}; window.__last['/api/gpt-draft'] = { json: json };
    if (json && json.proposed_text) { injectProposedText(json.proposed_text); window.toast && window.toast('Draft ready', 'success'); }
    else { window.toast && window.toast('Draft API returned no proposed_text', 'warn'); }
  }
  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('btnGetAIDraft') ||
      Array.prototype.slice.call(document.querySelectorAll('button')).find(function (b) {
        return /get ai draft/i.test((b.textContent || ''));
      });
    if (btn) btn.addEventListener('click', onGetAIDraft, { once: false });
  });
})();
