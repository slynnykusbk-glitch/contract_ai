import { describe, it, expect, vi } from 'vitest';

function mkEnv() {
  const handlers: Record<string, ((ev: any) => void)[]> = {};
  const docHandlers: Record<string, ((ev: any) => void)[]> = {};
  const win: any = {
    addEventListener: (n: string, f: any) => { (handlers[n] ||= []).push(f); },
    dispatchEvent: (ev: Event) => { (handlers[ev.type] || []).forEach(fn => fn(ev)); },
    location: { search: '' },
  };
  const prog = { className: 'progress', style: { display: 'block' } };
  const doc: any = {
    getElementById: (id: string) => (id === 'progress' ? prog : null),
    querySelector: () => null,
    querySelectorAll: (sel: string) => (sel === '.progress' ? [prog] : []),
    addEventListener: (n: string, f: any) => { (docHandlers[n] ||= []).push(f); },
    dispatchEvent: (ev: Event) => { (docHandlers[ev.type] || []).forEach(fn => fn(ev)); },
    visibilityState: 'visible',
    hidden: false,
  };
  let aborted = false;
  (globalThis as any).fetch = (_: any, opts: any = {}) =>
    new Promise((_res, rej) => {
      const sig = opts.signal;
      if (sig) sig.addEventListener('abort', () => {
        aborted = true;
        rej(new DOMException('aborted', 'AbortError'));
      });
    });
  (globalThis as any).window = win;
  (globalThis as any).document = doc;
  (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
  (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } } as any;
  (globalThis as any).Word = { Revision: {}, Comment: {}, SearchOptions: {}, ContentControl: {} } as any;
  (globalThis as any).__CAI_TESTING__ = true;
  return { win, doc, wasAborted: () => aborted };
}

describe('unload handling', () => {
  it('pagehide aborts only requests from same window', async () => {
    vi.resetModules();
    const env1 = mkEnv();
    const { invokeBootstrap: boot1 } = await import('../assets/taskpane.ts');
    boot1();
    const { postJson: post1 } = await import('../assets/api-client.ts');
    const p1 = post1('/x', {});

    vi.resetModules();
    const env2 = mkEnv();
    const { invokeBootstrap: boot2 } = await import('../assets/taskpane.ts');
    boot2();
    const { postJson: post2 } = await import('../assets/api-client.ts');
    const p2 = post2('/x', {});

    env1.win.dispatchEvent(new Event('pagehide'));
    await expect(p1).rejects.toThrow();
    expect(env1.wasAborted()).toBe(true);
    expect(env2.wasAborted()).toBe(false);

    env2.win.dispatchEvent(new Event('pagehide'));
    await expect(p2).rejects.toThrow();
    expect(env2.wasAborted()).toBe(true);
  });

  it('visibilitychange does not abort by default', async () => {
    vi.resetModules();
    const { win, doc, wasAborted } = mkEnv();
    const { invokeBootstrap } = await import('../assets/taskpane.ts');
    invokeBootstrap();
    const { postJson } = await import('../assets/api-client.ts');
    const p = postJson('/x', {});
    doc.visibilityState = 'hidden';
    doc.hidden = true;
    doc.dispatchEvent(new Event('visibilitychange'));
    await Promise.resolve();
    expect(wasAborted()).toBe(false);
    win.dispatchEvent(new Event('pagehide'));
    await expect(p).rejects.toThrow();
    expect(wasAborted()).toBe(true);
  });
});
