import { applyMetaToBadges, apiHealth, apiAnalyze, apiQaRecheck } from "./api-client";
import { notifyOk, notifyErr } from "./notifier";
import { getWholeDocText } from "./office"; // у вас уже есть хелпер; если имя иное — поправьте импорт.

type Mode = "live" | "friendly" | "doctor";

// --- helpers to locate and fill the "Proposed draft" textarea ---
function findProposedTextarea(): HTMLTextAreaElement | null {
  const primarySel = '#proposedText, textarea[name="proposed"], [data-role="proposed-text"]';
  let el = document.querySelector(primarySel) as HTMLTextAreaElement | null;
  if (el) return el;

  // Фолбэк: ищем textarea по тексту окружения
  const all = Array.from(document.querySelectorAll<HTMLTextAreaElement>('textarea'));
  return all.find(t => {
    const around =
      (t.getAttribute('placeholder') || '') + ' ' +
      (t.id || '') + ' ' + (t.name || '') + ' ' +
      (t.closest('.card, .form-group, section')?.textContent || '');
    return /proposed|suggest(ed)? edits|draft/i.test(around);
  }) || null;
}

function injectProposedText(text: string) {
  const target = findProposedTextarea();
  if (!target) {
    // мягкое уведомление: места для вставки не нашли
    (window as any).toast?.('Draft created, but target field not found', 'warn');
    return;
  }
  target.value = text || '';
  target.dispatchEvent(new Event('input', { bubbles: true }));
}

// --- handler for "Get AI Draft" ---
async function onGetAIDraft(ev?: Event) {
  ev?.preventDefault?.();

  const original =
    (document.getElementById('originalClause') as HTMLTextAreaElement | null)?.value?.trim() || '';

  const body = {
    text: original || 'Please propose a neutral confidentiality clause.',
    mode: 'friendly',
    before_text: '',
    after_text: '',
  };

  const resp = await fetch('/api/gpt-draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  // применим мета-бейджи, если они есть
  try {
    // эти функции уже есть в api-client.js
    // @ts-ignore
    const { metaFromResponse, applyMetaToBadges } = await import('./api-client.js');
    applyMetaToBadges(metaFromResponse(resp));
  } catch {}

  const json = await resp.json();
  (window as any).__last = (window as any).__last || {};
  (window as any).__last['/api/gpt-draft'] = { json };

  if (json?.proposed_text) {
    injectProposedText(json.proposed_text);
    (window as any).toast?.('Draft ready', 'success');
  } else {
    (window as any).toast?.('Draft API returned no proposed_text', 'warn');
  }
}

// навешиваем обработчик
document.addEventListener('DOMContentLoaded', () => {
  const btn =
    document.getElementById('btnGetAIDraft') ||
    Array.from(document.querySelectorAll('button')).find(b => /get ai draft/i.test(b.textContent || ''));
  if (btn) btn.addEventListener('click', onGetAIDraft, { once: false });
});

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
