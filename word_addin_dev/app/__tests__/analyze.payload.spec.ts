import { describe, it, expect, vi } from 'vitest';

describe('analyze payload wrapper', () => {
  it('wraps text under payload with schema and mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status:200 });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).window = { } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const { analyze } = await import('../assets/api-client.ts');
    await analyze({ text: 'hello', mode: 'live' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, opts] = fetchMock.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toHaveProperty('payload');
    expect(body.payload).toMatchObject({ schema: '1.4', mode: 'live', text: 'hello' });
  });
});
