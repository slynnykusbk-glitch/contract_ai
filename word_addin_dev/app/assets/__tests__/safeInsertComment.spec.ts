import { describe, it, expect, vi, afterEach } from 'vitest';
import { safeInsertComment } from '../annotate.ts';

describe('safeInsertComment', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetAllMocks();
  });

  it('warns when comment insertion fails', async () => {
    const sync = vi.fn().mockResolvedValue(undefined);
    const range: any = {
      context: { document: {}, sync },
      insertComment: vi.fn(() => { throw new Error('fail'); }),
    };
    (range.context.document as any).comments = { add: vi.fn(() => { throw new Error('fail'); }) };

    const notifyWarn = vi.fn();
    const logRichError = vi.fn();
    vi.stubGlobal('notifyWarn', notifyWarn);
    vi.stubGlobal('logRichError', logRichError);
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    await safeInsertComment(range, 'oops');

    expect(notifyWarn).toHaveBeenCalledWith('Failed to insert comment');
    expect(logRichError).toHaveBeenCalled();
  });
});
