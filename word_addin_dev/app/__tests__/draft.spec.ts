import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const html = readFileSync(
  new URL('../../../contract_review_app/contract_review_app/static/panel/taskpane.html', import.meta.url),
  'utf-8',
);

describe('get draft', () => {
  let fetchMock: any;
  beforeEach(() => {
    vi.resetModules();
    const dom = new JSDOM(html, { url: 'https://localhost:9443' });
    (globalThis as any).window = dom.window as any;
    (globalThis as any).document = dom.window.document as any;
    (globalThis as any).Event = dom.window.Event;
    (globalThis as any).CustomEvent = dom.window.CustomEvent;
    (globalThis as any).localStorage = {
      store: {} as Record<string, string>,
      getItem(key: string) { return this.store[key] || null; },
      setItem(key: string, value: string) { this.store[key] = value; }
    };
    fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status:200 });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).Office = {
      onReady: (cb: any) => cb({ host: 'Word' }),
      context: {
        requirements: { isSetSupported: () => true },
        host: 'Word',
        document: { addHandlerAsync: (_: any, cb: any) => { (globalThis as any).__selHandler = cb; } },
      },
      EventType: { DocumentSelectionChanged: 'DocumentSelectionChanged' },
    };
    (globalThis as any).__CAI_TESTING__ = true;
  });

  it('btnDraft disabled with empty text and no selection', async () => {
    const { wireUI, onSuggestEdit } = await import('../assets/taskpane.ts');
    wireUI();
    const btn = document.getElementById('btnSuggestEdit') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    await onSuggestEdit();
    const calls = fetchMock.mock.calls.filter((c: any[]) => String(c[0]).includes('/api/gpt/draft'));
    expect(calls.length).toBe(0);
  });

  it('selection enables and sends request with clause', async () => {
    (globalThis as any).getSelectionText = vi.fn().mockResolvedValue('This is a sample clause with sufficient length.');
    const { wireUI, getClauseText, onSuggestEdit } = await import('../assets/taskpane.ts');
    wireUI();
    await getClauseText();
    const btn = document.getElementById('btnSuggestEdit') as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    await onSuggestEdit();
    const calls = fetchMock.mock.calls.filter((c: any[]) => String(c[0]).includes('/api/gpt/draft'));
    expect(calls.length).toBe(1);
    const body = JSON.parse(calls[0][1].body);
    expect(body).toMatchObject({ clause: 'This is a sample clause with sufficient length.' });
  });

  it('Word API failure warns and skips request', async () => {
    (globalThis as any).getSelectionText = vi.fn().mockRejectedValue(new Error('fail'));
    vi.mock('../assets/notifier.ts', () => ({ notifyWarn: vi.fn(), notifyErr: vi.fn(), notifyOk: vi.fn() }));
    const { wireUI, onSuggestEdit } = await import('../assets/taskpane.ts');
    const { notifyWarn } = await import('../assets/notifier.ts');
    wireUI();
    await onSuggestEdit();
    const calls = fetchMock.mock.calls.filter((c: any[]) => String(c[0]).includes('/api/gpt/draft'));
    expect(calls.length).toBe(0);
    expect(notifyWarn).toHaveBeenCalledWith('Please paste the original clause (min 20 chars) or select text in the document.');
  });
});
