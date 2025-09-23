import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const html = readFileSync(
  new URL(
    '../../../contract_review_app/contract_review_app/static/panel/taskpane.html',
    import.meta.url
  ),
  'utf-8'
);

describe('no text blocks analyze', () => {
  let fetchMock: any;
  beforeEach(async () => {
    vi.resetModules();
    const dom = new JSDOM(html, { url: 'https://127.0.0.1:9443' });
    (globalThis as any).window = dom.window as any;
    (globalThis as any).document = dom.window.document as any;
    (globalThis as any).Event = dom.window.Event;
    (globalThis as any).CustomEvent = dom.window.CustomEvent;
    (globalThis as any).localStorage = {
      store: { api_key: 'k', schema_version: '1.4', backendUrl: 'https://127.0.0.1:9443' },
      getItem(key: string) {
        return (this.store as any)[key] || null;
      },
      setItem(key: string, value: string) {
        (this.store as any)[key] = value;
      },
    };
    fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).Office = {
      onReady: (cb: any) => cb({ host: 'Word' }),
      context: { requirements: { isSetSupported: () => true }, host: 'Word' },
    };
    (globalThis as any).Word = {
      Revision: {},
      Comment: {},
      SearchOptions: {},
      ContentControl: {},
      run: (fn: any) =>
        fn({
          document: { body: { text: '', load: () => {} } },
          sync: async () => {},
        }),
    };
    (globalThis as any).__CAI_TESTING__ = true;
  });

  it('skips analyze when no text', async () => {
    const { invokeBootstrap } = await import('../assets/taskpane.ts');
    invokeBootstrap();
    await Promise.resolve();
    await Promise.resolve();

    const btnWhole = document.getElementById('btnUseWholeDoc') as HTMLButtonElement;
    btnWhole.click();
    await new Promise(r => setTimeout(r, 0));
    const orig = document.getElementById('originalText') as HTMLTextAreaElement;
    expect(orig.value).toBe('');

    const btnAnalyze = document.getElementById('btnAnalyze') as HTMLButtonElement;
    btnAnalyze.disabled = false;
    btnAnalyze.click();

    const analyzeCalls = fetchMock.mock.calls.filter((c: any[]) =>
      String(c[0]).includes('/api/analyze')
    );
    expect(analyzeCalls.length).toBe(0);
  });
});
