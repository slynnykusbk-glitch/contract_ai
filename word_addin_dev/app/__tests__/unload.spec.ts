import { describe, it, expect } from 'vitest';

const mkEnv = () => {
  const handlers: Record<string, ((ev: any) => void)[]> = {};
  const docHandlers: Record<string, ((ev: any) => void)[]> = {};
  const win: any = {
    addEventListener: (n: string, f: any) => { (handlers[n]||(handlers[n]=[])).push(f); },
    dispatchEvent: (ev: Event) => { (handlers[ev.type]||[]).forEach(fn => fn(ev)); },
  };
  const prog = { className: 'progress', style: { display: 'block' } };
  const doc: any = {
    getElementById: (id: string) => id === 'progress' ? prog : null,
    querySelector: () => null,
    querySelectorAll: (sel: string) => sel === '.progress' ? [prog] : [],
    addEventListener: (n: string, f: any) => { (docHandlers[n]||(docHandlers[n]=[])).push(f); },
    dispatchEvent: (ev: Event) => { (docHandlers[ev.type]||[]).forEach(fn => fn(ev)); },
    visibilityState: 'visible',
    hidden: false,
  };
  (globalThis as any).window = win;
  (globalThis as any).document = doc;
  (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
  (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } } as any;
  (globalThis as any).Word = { Revision: {}, Comment: {}, SearchOptions: {}, ContentControl: {} } as any;
  (globalThis as any).__CAI_TESTING__ = true;
  return { handlers, win, doc };
};

describe('unload cleanup', () => {
  it('ignores visibilitychange but aborts on pagehide', async () => {
    const { win, doc } = mkEnv();
    let aborted = false;
    (globalThis as any).fetch = (_:any, opts:any = {}) => new Promise((_res, rej) => {
      const sig = opts.signal;
      if (sig) sig.addEventListener('abort', () => { aborted = true; rej(new DOMException('aborted','AbortError')); });
    });
    const { invokeBootstrap } = await import('../assets/taskpane.ts');
    invokeBootstrap();
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/x', {});
    doc.visibilityState = 'hidden';
    doc.hidden = true;
    doc.dispatchEvent(new Event('visibilitychange'));
    await Promise.resolve();
    expect(aborted).toBe(false);
    win.dispatchEvent(new Event('pagehide'));
    await expect(p).rejects.toThrow();
    expect(aborted).toBe(true);
  });
});
