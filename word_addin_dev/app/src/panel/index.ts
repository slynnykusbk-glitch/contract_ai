import { notifyOk, notifyWarn } from '../../assets/notifier';
import { ensureHeadersSet as ensureHeadersAuto } from '../../../../contract_review_app/frontend/common/http';

const $ = <T extends HTMLElement = HTMLElement>(sel: string) =>
  document.querySelector(sel) as T | null;
const show = (el: HTMLElement | null) => { if (el) el.hidden = false; };
const hide = (el: HTMLElement | null) => { if (el) el.hidden = true; };

export function wireDom() {
  $<HTMLButtonElement>('#btnInsertIntoWord')?.addEventListener('click', onInsertIntoWord);
}

export function onDraftReady() {
  show($('#btnInsertIntoWord'));
}

export async function onInsertIntoWord() {
  const txt = ($<HTMLTextAreaElement>('#txtDraft')?.value ?? '').trim();
  if (!txt) { notifyWarn('No draft text'); return; }
  await Word.run(async (ctx) => {
    const sel = ctx.document.getSelection();
    sel.insertText(txt, Word.InsertLocation.replace);
    await ctx.sync();
  }).catch(e => console.error('Word.run failed', e));
}

function enableAnalyzeUI(enable: boolean) {
  const btn = $<HTMLButtonElement>('#btnAnalyze');
  if (btn) btn.disabled = !enable;
}

export async function startPanel() {
  await Office.onReady();
  wireDom();
  await (async () => ensureHeadersAuto())();
  enableAnalyzeUI(true);
  notifyOk('Panel init OK');
}

if (!(globalThis as { __CAI_TESTING__?: boolean }).__CAI_TESTING__) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { void startPanel(); });
  } else {
    void startPanel();
  }
}

