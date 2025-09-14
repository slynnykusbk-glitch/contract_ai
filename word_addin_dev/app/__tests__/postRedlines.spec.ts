import { describe, it, expect, vi } from 'vitest';
describe('postRedlines', () => {
  it('sends two fields', async () => {
    (globalThis as any).window = { dispatchEvent() {} } as any;
    (globalThis as any).localStorage = { getItem: () => null } as any;
    (globalThis as any).fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: () => Promise.resolve({}),
    });
    const mod = await import('../assets/api-client');
    await mod.postRedlines('a', 'b');
    const [, opts] = (globalThis.fetch as any).mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toEqual({ before_text: 'a', after_text: 'b', schema: '1.4' });
    expect(opts.headers['x-schema-version']).toBe('1.4');
  });
});
