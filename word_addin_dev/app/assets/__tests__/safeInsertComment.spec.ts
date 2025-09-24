import { describe, it, expect, vi, afterEach } from 'vitest';
import { safeInsertComment } from '../annotate.ts';

describe('safeInsertComment', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
  });

  it('returns false when WordApi 1.4 not supported', async () => {
    const isSetSupported = vi.fn().mockReturnValue(false);
    vi.stubGlobal('Office', { context: { requirements: { isSetSupported } } });
    const ok = await safeInsertComment({} as any, 'x');
    expect(ok).toBe(false);
    expect(isSetSupported).toHaveBeenCalledWith('WordApi', '1.4');
  });

  it('returns false on NotImplemented errors', async () => {
    const isSetSupported = vi.fn().mockReturnValue(true);
    vi.stubGlobal('Office', { context: { requirements: { isSetSupported } } });
    const err: any = new Error('ni');
    err.code = 'NotImplemented';
    const sync = vi.fn();
    const range: any = {
      context: { document: { comments: { add: vi.fn(() => { throw err; }) } }, sync },
      insertComment: vi.fn(() => { throw err; }),
    };
    (range.context.document as any).comments = { add: vi.fn(() => { throw new Error('fail'); }) };

    const notifyWarn = vi.fn();
    const logRichError = vi.fn();
    vi.stubGlobal('notifyWarn', notifyWarn);
    vi.stubGlobal('logRichError', logRichError);
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    const res = await safeInsertComment(range, 'oops');

    expect(res.ok).toBe(false);
    expect(notifyWarn).toHaveBeenCalledWith('Failed to insert comment');
    expect(logRichError).toHaveBeenCalled();

  });
});
