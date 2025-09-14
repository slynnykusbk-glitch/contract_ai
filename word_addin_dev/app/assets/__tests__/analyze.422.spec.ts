import { describe, it, expect, vi } from 'vitest';

(globalThis as any).window = { addEventListener() {}, dispatchEvent() {} } as any;
(globalThis as any).document = { addEventListener() {}, querySelectorAll() { return [] as any; } } as any;

vi.mock('../notifier.ts', () => ({ notifyWarn: vi.fn(), notifyErr: vi.fn(), notifyOk: vi.fn() }));

describe('analyze 422 diagnostics', () => {
  it('logs detail and notifies', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      headers: new Headers(),
      json: async () => ({ detail: [{ loc: ['body','payload'], msg: 'bad' }] })
    });
    (globalThis as any).fetch = fetchMock;
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { analyze } = await import('../api-client.ts');
    const { notifyWarn } = await import('../notifier.ts');
    await analyze({ text: 'x' });
    expect(warnSpy).toHaveBeenCalledWith('[analyze] 422', [{ loc: ['body','payload'], msg: 'bad' }]);
    expect(notifyWarn).toHaveBeenCalledWith('Validation error: bad');
    warnSpy.mockRestore();
  });
});
