import { describe, it, expect } from 'vitest';

describe('health positive', () => {
  it('returns ok', async () => {
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).fetch = async () => ({ ok: true, json: async () => ({}) , headers: new Headers(), status:200 });
    const { apiHealth } = await import('../assets/api-client.ts');
    const res = await apiHealth();
    expect(res.ok).toBe(true);
  });
});
