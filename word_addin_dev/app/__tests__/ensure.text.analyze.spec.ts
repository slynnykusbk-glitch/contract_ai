import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const html = readFileSync(
  new URL('../../../contract_review_app/contract_review_app/static/panel/taskpane.html', import.meta.url),
  'utf-8',
);

describe('ensure text for analyze', () => {
  let fetchMock: any;
  beforeEach(() => {
    vi.resetModules();
    const dom = new JSDOM(html, { url: 'https://localhost:9443' });
    (globalThis as any).window = dom.window as any;
    (globalThis as any).document = dom.window.document as any;
    (globalThis as any).Event = dom.window.Event;
    (globalThis as any).CustomEvent = dom.window.CustomEvent;
    (globalThis as any).localStorage = {
      store: { api_key: 'k', schema_version: '1.4', backendUrl: 'https://localhost:9443' },
      getItem(key: string) { return (this.store as any)[key] || null; },
      setItem(key: string, value: string) { (this.store as any)[key] = value; }
    };
    fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status:200 });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).Office = {
      onReady: (cb: any) => cb({ host: 'Word' }),
      context: { requirements: { isSetSupported: () => true }, host: 'Word' }
    };
    (globalThis as any).__CAI_TESTING__ = true;
  });

  it('reads whole doc when textarea empty', async () => {
    const getWholeDocText = vi.fn().mockResolvedValue('Hello');
    (globalThis as any).getWholeDocText = getWholeDocText;
    const { onAnalyze } = await import('../assets/taskpane.ts');
    await onAnalyze();
    expect(getWholeDocText).toHaveBeenCalledOnce();
    const analyzeCalls = fetchMock.mock.calls.filter((c: any[]) => String(c[0]).includes('/api/analyze'));
    expect(analyzeCalls.length).toBe(1);
    const body = JSON.parse(analyzeCalls[0][1].body);
    expect(body.text.length).toBeGreaterThan(0);
    expect(body).toMatchObject({ schema: '1.4', mode: 'live' });
  });

  it('warns when document empty', async () => {
    const getWholeDocText = vi.fn().mockResolvedValue('');
    (globalThis as any).getWholeDocText = getWholeDocText;
    vi.mock('../assets/notifier.ts', () => ({ notifyWarn: vi.fn(), notifyErr: vi.fn(), notifyOk: vi.fn() }));
    const { onAnalyze } = await import('../assets/taskpane.ts');
    const { notifyWarn } = await import('../assets/notifier.ts');
    await onAnalyze();
    expect(getWholeDocText).toHaveBeenCalledOnce();
    const analyzeCalls = fetchMock.mock.calls.filter((c: any[]) => String(c[0]).includes('/api/analyze'));
    expect(analyzeCalls.length).toBe(0);
    expect(notifyWarn).toHaveBeenCalledWith('Document is empty');
  });
});
