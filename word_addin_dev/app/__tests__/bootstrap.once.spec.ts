import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('bootstrap once', () => {
  beforeEach(() => { vi.resetModules(); });
  it('invokes wireUI only once', async () => {
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).window = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => {} };
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } } as any;
    (globalThis as any).Word = { Revision:{}, Comment:{}, SearchOptions:{}, ContentControl:{} } as any;
    (globalThis as any).document = { querySelector: () => null, getElementById: () => null, addEventListener: () => {} } as any;
    const mod = await import('../assets/taskpane.ts');
    mod.invokeBootstrap();
    mod.invokeBootstrap();
    expect(mod.getBootstrapCount()).toBe(1);
  });
});
