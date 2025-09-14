import { describe, it, expect, vi } from 'vitest';

(globalThis as any).window = { addEventListener() {}, dispatchEvent() {} } as any;
(globalThis as any).document = { addEventListener() {}, querySelectorAll() { return [] as any; } } as any;

describe('analyze request body', () => {
  it('sends flat payload when given text only', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: async () => ({}) });
    (globalThis as any).fetch = fetchMock;
    const { analyze } = await import('../api-client.ts');
    await analyze({ text: 'hi' });
    const { headers, body: bodyStr } = fetchMock.mock.calls[0][1];
    const body = JSON.parse(bodyStr);
    expect(body).toMatchObject({ text: 'hi', mode: 'live', schema: '1.4' });
    expect(headers['x-schema-version']).toBe('1.4');
  });

  it('ignores provided schema but preserves mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: async () => ({}) });
    (globalThis as any).fetch = fetchMock;
    const { analyze } = await import('../api-client.ts');
    await analyze({ schema: '1.4', mode: 'test', text: 'hi' });
    const { headers, body: bodyStr } = fetchMock.mock.calls[0][1];
    const body = JSON.parse(bodyStr);
    expect(body).toMatchObject({ text: 'hi', mode: 'test', schema: '1.4' });
    expect(headers['x-schema-version']).toBe('1.4');
  });
});
