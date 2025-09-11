import { describe, it, expect } from 'vitest';

describe('onInsertIntoWord', () => {
  it('does not throw when DOM elements are missing', async () => {
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).document = {
      querySelector: () => null,
      getElementById: () => null,
    } as any;
    const mod = await import('../src/panel/index');
    await expect(mod.onInsertIntoWord()).resolves.toBeUndefined();
  });
});
