import { describe, it, expect, vi } from 'vitest';

describe('analyze payload wrapper', () => {
  it('sends flat payload with mode only', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).window = { dispatchEvent() {} } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const { analyze } = await import('../assets/api-client.ts');
    await analyze({ text: 'hello', mode: 'live' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, opts] = fetchMock.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toMatchObject({ mode: 'live', text: 'hello', schema: '1.4', risk: 'medium' });
    expect('payload' in body).toBe(false);
    expect(opts.headers['x-schema-version']).toBe('1.4');
  });
});
