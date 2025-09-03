const input = document.getElementById('input') as HTMLTextAreaElement;
const output = document.getElementById('output') as HTMLPreElement;

const isOk = (s: any) => String(s).toLowerCase() === 'ok';
const getSchemaVer = (b: any) => (b?.x_schema_version || b?.schema_version || null);

async function callApi(endpoint: string) {
  output.textContent = '...';
  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: input.value})
    });
    const data = await resp.json();
    getSchemaVer(data);
    if (!resp.ok || !isOk(data.status) || !isOk(data?.analysis?.status)) {
      throw new Error(JSON.stringify(data));
    }
    output.textContent = JSON.stringify(data, null, 2);
  } catch (err: any) {
    output.textContent = err.message || String(err);
  }
}

function onClick(id: string, handler: (ev: MouseEvent) => any) {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener('click', handler);
}

onClick('btnAnalyze', () => callApi('/api/analyze'));
onClick('btnSummary', () => callApi('/api/summary'));
onClick('btnSuggest', () => callApi('/api/suggest_edits'));
onClick('btnQA', () => callApi('/api/qa-recheck'));

async function pingHealth() {
  const badge = document.getElementById('health');
  if (!badge) return;
  try {
    const r = await fetch('/health');
    badge.textContent = r.ok ? 'ok' : 'fail';
    badge.className = r.ok ? 'ok' : 'fail';
  } catch {
    badge.textContent = 'fail';
    badge.className = 'fail';
  }
}

pingHealth();
