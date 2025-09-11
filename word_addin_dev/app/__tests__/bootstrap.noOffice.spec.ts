import { describe, it, expect, vi } from 'vitest';
describe('bootstrapHeaders', () => {
  it('resolves without Office context', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).fetch = vi.fn().mockRejectedValue(new Error('no network'));
    (globalThis as any).localStorage = {
      getItem: () => null,
      setItem: vi.fn(),
    } as any;
    const mod = await import('../assets/bootstrap.ts');
    await expect(mod.bootstrapHeaders()).resolves.toBeUndefined();
  });
});
