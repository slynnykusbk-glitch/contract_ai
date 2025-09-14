import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const html = readFileSync(
  new URL('../../../contract_review_app/contract_review_app/static/panel/taskpane.html', import.meta.url),
  'utf-8',
);

describe('qa recheck navigation', () => {
  beforeEach(() => {
    vi.resetModules();
    const dom = new JSDOM(html, { url: 'https://localhost:9443' });
    (globalThis as any).window = dom.window as any;
    (globalThis as any).document = dom.window.document as any;
    (globalThis as any).Event = dom.window.Event;
    (globalThis as any).CustomEvent = dom.window.CustomEvent;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} };
    (globalThis as any).Office = {
      onReady: (cb: any) => cb({ host: 'Word' }),
      context: {
        requirements: { isSetSupported: () => true },
        host: 'Word',
        document: { addHandlerAsync: (_: any, cb: any) => { (globalThis as any).__selHandler = cb; } },
      },
      EventType: { DocumentSelectionChanged: 'DocumentSelectionChanged' },
    };
    (globalThis as any).Word = { run: async () => {}, SearchOptions: {}, Comment: {}, Revision: {}, ContentControl: {} };
    (globalThis as any).__CAI_TESTING__ = true;
  });

  it('qa recheck replaces findings with api response', async () => {
    const qaResp = { analysis: { findings: [{ rule_id: 'r1', snippet: 'A', start: 0, end: 1 }] } };
    vi.doMock('../assets/api-client.ts', () => ({
      postJSON: vi.fn(async () => ({ json: qaResp })),
      applyMetaToBadges: () => {},
      parseFindings: (resp: any) => resp.analysis.findings,
      analyze: vi.fn(),
    }));
    const mod = await import('../assets/taskpane.ts');

    const resultsEl = document.getElementById('results')!;
    resultsEl.addEventListener('ca.qa', (e: any) => {
      const arr = e.detail.analysis.findings;
      (window as any).__findings = arr;
      const fl = document.getElementById('findingsList')!;
      fl.innerHTML = '';
      arr.forEach((f: any) => {
        const li = document.createElement('li') as any;
        li.textContent = JSON.stringify(f);
        li.scrollIntoView = () => {};
        fl.appendChild(li);
      });
    });

    mod.wireUI();

    (window as any).__findings = [
      { rule_id: 'r1', snippet: 'A', start: 0, end: 1 },
      { rule_id: 'r1', snippet: 'A', start: 0, end: 1 },
      { rule_id: 'r2', snippet: 'B', start: 2, end: 3 },
    ];
    const fl = document.getElementById('findingsList')!;
    fl.innerHTML = '';
    (window as any).__findings.forEach((f: any) => {
      const li = document.createElement('li') as any;
      li.textContent = JSON.stringify(f);
      li.scrollIntoView = () => {};
      fl.appendChild(li);
    });

    const next = document.getElementById('btnNextIssue') as HTMLButtonElement;
    for (let i = 0; i < 10; i++) next.click();

    const qaBtn = document.getElementById('btnQARecheck') as HTMLButtonElement;
    qaBtn.click();
    await new Promise(r => setTimeout(r, 0));

    const items = (window as any).__findings;
    expect(items).toEqual(qaResp.analysis.findings);
    expect(document.getElementById('findingsList')!.children.length).toBe(1);
    const uniq = new Set(items.map((f: any) => `${f.rule_id}|${f.start}|${f.end}`));
    expect(uniq.size).toBe(items.length);
    expect(items.find((f: any) => f.rule_id === 'r2')).toBeUndefined();
  });
});
