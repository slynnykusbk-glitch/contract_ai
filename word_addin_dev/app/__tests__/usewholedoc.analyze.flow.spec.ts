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

describe('use whole doc + analyze flow', () => {
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
          document: { body: { text: 'TEST BODY', load: () => {} } },
          sync: async () => {},
        }),
    };
    (globalThis as any).__CAI_TESTING__ = true;
  });

  it('loads doc and posts analyze', async () => {
    vi.useFakeTimers();
    const { invokeBootstrap } = await import('../assets/taskpane.ts');
    invokeBootstrap();
    await Promise.resolve();
    await Promise.resolve();

    const btnWhole = document.getElementById('btnUseWholeDoc') as HTMLButtonElement;
    btnWhole.click();
    await vi.advanceTimersByTimeAsync(0);
    const orig = document.getElementById('originalText') as HTMLTextAreaElement;
    expect(orig.value).toBe('TEST BODY');

    const btnAnalyze = document.getElementById('btnAnalyze') as HTMLButtonElement;
    btnAnalyze.disabled = false;
    fetchMock.mockImplementationOnce(
      () =>
        new Promise(res =>
          setTimeout(
            () => res({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 }),
            50
          )
        )
    );
    btnAnalyze.click();
    const book = document.getElementById('loading-book') as HTMLElement;
    await Promise.resolve();
    expect(book.classList.contains('hidden')).toBe(false);
    await vi.advanceTimersByTimeAsync(60);
    await Promise.resolve();
    expect(book.classList.contains('hidden')).toBe(true);
    const analyzeCalls = fetchMock.mock.calls.filter((c: any[]) =>
      String(c[0]).includes('/api/analyze')
    );
    expect(analyzeCalls.length).toBe(1);
    const opts = analyzeCalls[0][1];
    const body = JSON.parse(opts.body);
    expect(body).toMatchObject({ mode: 'live', text: 'TEST BODY', schema: '1.4' });
    expect(opts.headers['x-schema-version']).toBe('1.4');
    vi.useRealTimers();
  }, 10000);
});
