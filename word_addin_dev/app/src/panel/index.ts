import { notify } from '../../assets/notifier';
import { metaFromResponse, applyMetaToBadges } from '../../assets/api-client';

const backend = (window as any).CAI?.Store?.getBase?.() || 'https://localhost:9443';

/** Достаём целиком текст документа Word */
async function getWholeDocText(): Promise<string> {
  return await Word.run(async ctx => {
    const body = ctx.document.body;
    body.load('text');
    await ctx.sync();
    return (body.text || '').trim();
  });
}

async function postJson(path: string, body: any): Promise<Response> {
  const resp = await fetch(`${backend}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  applyMetaToBadges(metaFromResponse(resp));
  return resp;
}

/** Кнопка Test — пинг модели */
async function onTest(e: Event) {
  e.preventDefault();
  const resp = await postJson('/api/gpt-draft', { text: 'Ping draft', mode: 'friendly' });
  const js = await resp.json();
  notify.ok(`LLM: HTTP ${resp.status}`);
  console.log('GPT-DRAFT resp:', js);
}

/** Analyze(doc) */
async function onAnalyzeDoc(e: Event) {
  e.preventDefault();
  const text = await getWholeDocText();
  if (!text) { notify.warn('В документе нет текста'); return; }
  const resp = await postJson('/api/analyze', { text, mode: 'live' });
  const js = await resp.json();
  notify.ok(`ANALYZE: HTTP ${resp.status}`);
  console.log('ANALYZE resp:', js);
}

/** QA Recheck — без правил (для smoke) */
async function onQARecheck(e: Event) {
  e.preventDefault();
  const text = await getWholeDocText();
  if (!text) { notify.warn('В документе нет текста'); return; }
  const resp = await postJson('/api/qa-recheck', { text, rules: [] });
  const js = await resp.json();
  notify.ok(`QA: HTTP ${resp.status}`);
  console.log('QA resp:', js);
}

function bindClick(sel: string, fn: (e: Event) => void) {
  const b = document.querySelector(sel) as HTMLButtonElement | null;
  if (!b) return;
  b.addEventListener('click', fn);
  b.classList.remove('btn-grey');
  b.disabled = false;
}

/** Инициализация строго после Office.onReady */
Office.onReady().then(() => {
  // backend base может задаваться из store; резерв — localhost
  if ((window as any).CAI?.Store?.setBase) {
    (window as any).CAI.Store.setBase('https://localhost:9443');
  }
  bindClick('#btnTest', onTest);
  bindClick('#btnAnalyzeDoc', onAnalyzeDoc);
  bindClick('#btnQARecheck', onQARecheck);
  notify.info('Panel init OK');
});
