import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('checkHealth negatives', () => {
  beforeEach(() => { vi.resetModules(); });

  it('handles non-ok response', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ foo: 1 }),
      headers: new Headers(),
      status: 500,
    });
    const { checkHealth } = await import('../assets/health.ts');
    const res = await checkHealth();
    expect(res.ok).toBe(false);
    expect(res.json).toEqual({ foo: 1 });
  });

  it('propagates fetch errors', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = vi.fn().mockRejectedValue(new Error('boom'));
    const { checkHealth } = await import('../assets/health.ts');
    await expect(checkHealth()).rejects.toThrow('boom');
  });
});
