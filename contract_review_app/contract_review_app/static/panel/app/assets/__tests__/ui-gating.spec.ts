import { describe, it, expect, vi } from 'vitest';

function stubEl(id: string) {
  const listeners: Record<string, Function[]> = {};
  return {
    id,
    disabled: true,
    title: '',
    value: '',
    textContent: '',
    style: {} as any,
    classList: { remove() {}, add() {} },
    addEventListener(type: string, fn: any) {
      (listeners[type] ||= []).push(fn);
    },
    removeAttribute(name: string) {
      if (name === 'disabled') this.disabled = false;
    },
    setAttribute() {},
    dispatchEvent(ev: any) {
      (listeners[ev.type] || []).forEach(fn => fn(ev));
      return true;
    },
    click() {
      if (this.disabled) return;
      (listeners['click'] || []).forEach(fn => fn({ preventDefault() {} }));
    },
  } as any;
}

describe('UI gating without comments API', () => {
  it('disables annotate/accept and prevents actions', async () => {
    const elements: Record<string, any> = {};
    const doc: any = {
      readyState: 'complete',
      getElementById(id: string) { return elements[id] || (elements[id] = stubEl(id)); },
      querySelector(sel: string) { return this.getElementById(sel.replace('#', '')); },
      createElement(tag: string) { return stubEl(tag); },
      body: { innerHTML: '', appendChild() {} },
      addEventListener() {},
    };
    (globalThis as any).document = doc;
    (globalThis as any).window = { addEventListener() {}, dispatchEvent() {} } as any;
    (globalThis as any).localStorage = { getItem() { return null; }, setItem() {}, removeItem() {} } as any;
    const wordRun = vi.fn();
    (globalThis as any).Word = { run: wordRun } as any;
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => false }, document: { addHandlerAsync() {} } }, onReady: () => {} } as any;
    const fetchMock = vi.fn();
    (globalThis as any).fetch = fetchMock;
    const annotateMock = vi.fn();
    (globalThis as any).annotateFindingsIntoWord = annotateMock;
    const safeInsertMock = vi.fn();
    (globalThis as any).safeInsertComment = safeInsertMock;
    const notifyWarn = vi.fn();
    vi.doMock('../notifier', () => ({ notifyOk: vi.fn(), notifyErr: vi.fn(), notifyWarn }));
    (globalThis as any).__CAI_TESTING__ = true;
    const mod = await import('../taskpane.ts');
    (globalThis as any).__CAI_TESTING__ = false;
    mod.wireUI();
    const annotateBtn = elements['btnAnnotate'];
    const acceptBtn = elements['btnAcceptAll'];
    expect(annotateBtn.disabled).toBe(true);
    expect(acceptBtn.disabled).toBe(true);
    expect(notifyWarn).toHaveBeenCalledWith('Comments API not available in this Word build');
    annotateBtn.click();
    acceptBtn.click();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(annotateMock).not.toHaveBeenCalled();
    expect(safeInsertMock).not.toHaveBeenCalled();
    expect(wordRun).not.toHaveBeenCalled();
  });
});
