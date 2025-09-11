import { describe, it, expect, vi } from 'vitest';
describe('apiHealth negatives', () => {
  it('handles non-ok response', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ foo: 1 }),
      headers: new Headers(),
      status: 500,
    });
    const mod = await import('./app/assets/api-client.ts');
    const res = await mod.apiHealth();
    expect(res.ok).toBe(false);
    expect(res.json).toEqual({ foo: 1 });
  });

  it('propagates fetch errors', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = vi.fn().mockRejectedValue(new Error('boom'));
    const mod = await import('./app/assets/api-client.ts');
    await expect(mod.apiHealth()).rejects.toThrow('boom');
  });
});
