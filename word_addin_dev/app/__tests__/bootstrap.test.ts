import { describe, it, expect, vi } from 'vitest';

describe('startPanel bootstrap', () => {
  it('waits for Office.onReady before wiring', async () => {
    (globalThis as any).__CAI_TESTING__ = true;
    const qSpy = vi.fn(() => null);
    (globalThis as any).document = {
      querySelector: qSpy,
      getElementById: () => null,
      addEventListener: () => {},
      readyState: 'complete'
    } as any;
    (globalThis as any).localStorage = { getItem: () => '', setItem: () => {} };
    (globalThis as any).fetch = vi.fn(async () => ({ json: async () => ({}) }));
    const mod = await import('../src/panel/index');
    let readyResolve: () => void;
    const onReady = vi.fn(() => new Promise<void>(res => { readyResolve = res; }));
    (globalThis as any).Office = { onReady };
    const p = mod.startPanel();
    expect(onReady).toHaveBeenCalled();
    expect(qSpy).not.toHaveBeenCalled();
    readyResolve();
    await p;
    expect(qSpy).toHaveBeenCalled();
  });
});
