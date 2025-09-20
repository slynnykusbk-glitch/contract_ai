import { describe, it, expect, vi } from 'vitest';
import type { components } from '../../../docs/api';

type AnalyzeRequest = components['schemas']['AnalyzeRequest'];

describe('analyze flow', () => {
  it('posts flat payload with schema', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).window = { dispatchEvent() {} } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const { analyze } = await import('../assets/api-client.ts');
    const payload: AnalyzeRequest = { text: 'hello', language: 'en-GB', mode: 'live', risk: null, schema: null };
    await analyze({ text: payload.text, mode: payload.mode } as any);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, opts] = fetchMock.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toMatchObject({ text: 'hello', mode: 'live', schema: '1.4', risk: 'medium' });
    expect(opts.headers['x-schema-version']).toBe('1.4');
  });
});
