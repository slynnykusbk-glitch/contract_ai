import { describe, it, expect, vi } from 'vitest';
import { JSDOM } from 'jsdom';

function setupDom() {
  const dom = new JSDOM('<div id="loading-book" class="cai-book hidden"></div>', {
    url: 'https://127.0.0.1',
  });
  (globalThis as any).window = dom.window as any;
  (globalThis as any).document = dom.window.document as any;
  (globalThis as any).CustomEvent = dom.window.CustomEvent;
  dom.window.addEventListener('cai:busy', (e: any) => {
    const el = dom.window.document.getElementById('loading-book');
    const busy = !!e?.detail?.busy;
    if (busy) el?.classList.remove('hidden');
    else el?.classList.add('hidden');
  });
  return dom;
}

describe('loading indicator', () => {
  it('shows during operation and hides after completion', async () => {
    vi.resetModules();
    const dom = setupDom();
    const { withBusy } = await import('../assets/pending.ts');
    const p = withBusy(async () => {
      await new Promise(r => setTimeout(r, 50));
    });
    await Promise.resolve();
    expect(dom.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      false
    );
    await p;
    expect(dom.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      true
    );
  });

  it('aggregates concurrent operations', async () => {
    vi.resetModules();
    const dom = setupDom();
    const { withBusy } = await import('../assets/pending.ts');
    const wait = (ms: number) => new Promise(r => setTimeout(r, ms));
    const p1 = withBusy(() => wait(20));
    const p2 = withBusy(() => wait(40));
    await Promise.resolve();
    expect(dom.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      false
    );
    await p1;
    expect(dom.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      false
    );
    await p2;
    expect(dom.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      true
    );
  });

  it('hides after rejected operation', async () => {
    vi.resetModules();
    const dom = setupDom();
    const { withBusy } = await import('../assets/pending.ts');
    await withBusy(async () => {
      throw new Error('x');
    }).catch(() => {});
    expect(dom.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      true
    );
  });

  it('isolates per window', async () => {
    const wait = (ms: number) => new Promise(r => setTimeout(r, ms));

    vi.resetModules();
    const dom1 = setupDom();
    const { withBusy: withBusy1 } = await import('../assets/pending.ts');
    await withBusy1(() => wait(20));
    expect(dom1.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      true
    );

    vi.resetModules();
    const dom2 = setupDom();
    const { withBusy: withBusy2 } = await import('../assets/pending.ts');
    expect(dom1.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      true
    );
    await withBusy2(() => wait(20));
    expect(dom2.window.document.getElementById('loading-book')?.classList.contains('hidden')).toBe(
      true
    );
  });
});
