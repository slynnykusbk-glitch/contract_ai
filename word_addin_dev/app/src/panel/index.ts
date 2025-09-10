import { notifyOk, notifyWarn } from '../../assets/notifier';
import { postJson } from './api-client';

let lastCid = '';

/** Достаём целиком текст документа Word */
async function getWholeDocText(): Promise<string> {
  return await Word.run(async ctx => {
    const body = ctx.document.body;
    body.load('text');
    await ctx.sync();
    return (body.text || '').trim();
  });
}

/** Выделенный текст (клаузула) */
async function getSelectedText(): Promise<string> {
  return await Word.run(async ctx => {
    const sel = ctx.document.getSelection();
    sel.load('text');
    await ctx.sync();
    return (sel.text || '').trim();
  });
}

function getLastCid(): string | null {
  return lastCid || null;
}

async function handleResponse(res: Response, label: string) {
  const js = await res.json().catch(() => ({}));
  const cid = res.headers.get('x-cid');
  if (cid) lastCid = cid;
  notifyOk(`${label}: HTTP ${res.status}`);
  console.log(`${label} resp:`, js);
}

// Analyze whole doc
async function doAnalyzeWholeDoc() {
  const text = await getWholeDocText();
  const res = await postJson('/api/analyze', { text });
  await handleResponse(res, 'Analyze');
}

// Draft using GPT
async function doGptDraft(clauseText: string) {
  const cid = getLastCid();
  if (!cid) throw new Error('NO_CID');
  const res = await postJson('/api/gpt-draft', { cid, clause: clauseText, mode: 'friendly' });
  await handleResponse(res, 'GPT Draft');
}

// Summary for last CID
async function doSummary() {
  const cid = getLastCid();
  const res = await postJson('/api/summary', { cid });
  await handleResponse(res, 'Summary');
}

async function doQARecheck(text: string) {
  const res = await postJson('/api/qa-recheck', { text, rules: {} });
  await handleResponse(res, 'QA');
}

function bindClick(sel: string, fn: (e: Event) => Promise<void>) {
  const b = document.querySelector(sel) as HTMLButtonElement | null;
  if (!b) return;
  b.addEventListener('click', async e => {
    try {
      await fn(e);
    } catch (err: any) {
      notifyWarn('Request failed');
    }
  });
  b.disabled = false;
}

Office.onReady().then(() => {
  bindClick('#btnAnalyze', async e => { e.preventDefault(); await doAnalyzeWholeDoc(); });
  bindClick('#btnSummary', async e => { e.preventDefault(); await doSummary(); });
  bindClick('#btnSuggest', async e => {
    e.preventDefault();
    const clause = await getSelectedText();
    if (!clause) { notifyWarn('Select clause text first'); return; }
    await doGptDraft(clause);
  });
  bindClick('#btnQA', async e => {
    e.preventDefault();
    const text = await getSelectedText();
    if (!text) { notifyWarn('Select clause text first'); return; }
    await doQARecheck(text);
  });
  notifyOk('Panel init OK');
});
