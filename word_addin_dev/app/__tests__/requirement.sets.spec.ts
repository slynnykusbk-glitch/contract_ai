import { describe, it, expect, beforeEach, vi } from 'vitest';

const mkDoc = (ids: string[]) => {
  const elements: Record<string, any> = {};
  ids.forEach(id => elements[id] = { disabled: false, style: { display: '' }, addEventListener: () => {}, classList: { remove: () => {} }, removeAttribute: () => {} });
  return {
    getElementById: (id: string) => elements[id] || null,
    querySelector: (sel: string) => elements[sel.replace('#','')] || null,
  } as any;
};

describe('requirement sets support', () => {
  beforeEach(() => {
    vi.resetModules();
    (globalThis as any).window = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => {} };
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } } as any;
  });

  it('disables revisions buttons when revisions unsupported', async () => {
    (globalThis as any).document = mkDoc(['btnApplyTracked','btnAcceptAll','btnRejectAll']);
    (globalThis as any).Word = { Comment: {}, SearchOptions: {}, ContentControl: {} } as any;
    const { wireUI } = await import('../assets/taskpane.ts');
    wireUI();
    const btn = document.getElementById('btnApplyTracked') as any;
    expect(btn.disabled).toBe(true);
  });

  it('disables comment features when comments unsupported', async () => {
    (globalThis as any).document = mkDoc(['btnAcceptAll']);
    (globalThis as any).Word = { Revision: {}, SearchOptions: {}, ContentControl: {} } as any;
    const { wireUI } = await import('../assets/taskpane.ts');
    wireUI();
    const btn = document.getElementById('btnAcceptAll') as any;
    expect(btn.disabled).toBe(true);
  });

  it('disables search navigation when search unsupported', async () => {
    (globalThis as any).document = mkDoc(['btnPrevIssue','btnNextIssue','btnQARecheck']);
    (globalThis as any).Word = { Revision: {}, Comment: {}, ContentControl: {} } as any;
    const { wireUI } = await import('../assets/taskpane.ts');
    wireUI();
    expect((document.getElementById('btnPrevIssue') as any).disabled).toBe(true);
    expect((document.getElementById('btnQARecheck') as any).disabled).toBe(true);
  });

  it('disables annotate when content controls unsupported', async () => {
    (globalThis as any).document = mkDoc(['btnAnnotate']);
    (globalThis as any).Word = { Revision: {}, Comment: {}, SearchOptions: {} } as any;
    const { wireUI } = await import('../assets/taskpane.ts');
    wireUI();
    expect((document.getElementById('btnAnnotate') as any).disabled).toBe(true);
  });
});
