import { describe, it, expect, vi } from 'vitest';

(globalThis as any).window = { addEventListener() {}, dispatchEvent() {} } as any;
(globalThis as any).document = { addEventListener() {}, querySelectorAll() { return [] as any; } } as any;

vi.mock('../notifier', () => ({ notifyWarn: vi.fn(), notifyErr: vi.fn(), notifyOk: vi.fn() }));

describe('analyze flat body', () => {
  it('does not trigger 422 when body is flat', async () => {
    const fetchMock = vi.fn(async (_url, opts: any) => {
      const hasPayload = 'payload' in JSON.parse(opts.body);
      return hasPayload
        ? { ok: false, status: 422, headers: new Headers(), json: async () => ({}) }
        : { ok: true, status: 200, headers: new Headers(), json: async () => ({}) };
    });
    (globalThis as any).fetch = fetchMock;
    const { analyze } = await import('../api-client');
    const res = await analyze({ text: 'x' });
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect('payload' in body).toBe(false);
    expect(res.resp.status).toBe(200);
  });
});
