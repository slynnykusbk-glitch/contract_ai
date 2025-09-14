import { describe, it, expect, vi } from 'vitest';

(globalThis as any).window = { addEventListener() {}, dispatchEvent() {} } as any;
(globalThis as any).document = { getElementById() { return null as any; }, querySelectorAll() { return [] as any; }, addEventListener() {} } as any;
(globalThis as any).CustomEvent = class {} as any;

describe('analyze request body', () => {
  it('sends text, mode and schema directly', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: async () => ({}) });
    (globalThis as any).fetch = fetchMock;
    const { analyze } = await import('../api-client.ts');
    await analyze({ text: 'hi', mode: 'live', schema: '1.4' });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toMatchObject({ text: 'hi', mode: 'live', schema: '1.4' });
  });
});
