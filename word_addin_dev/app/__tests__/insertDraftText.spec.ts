import { describe, it, expect, vi } from 'vitest';
import { insertDraftText } from '../assets/insert';

describe('insertDraftText', () => {
  it('skips empty text', async () => {
    const run = vi.fn();
    (globalThis as any).Word = { run };
    await insertDraftText('', 'live');
    expect(run).not.toHaveBeenCalled();
  });

  it('calls Word.run once', async () => {
    const run = vi.fn(async (cb: any) => {
      const sel = { isEmpty: true, load: vi.fn(), insertText: vi.fn().mockReturnValue({}) };
      const rangeEnd = { insertText: vi.fn().mockReturnValue({}) };
      const doc = {
        getSelection: () => sel,
        body: { getRange: () => rangeEnd },
        comments: { add: vi.fn() },
      };
      await cb({ document: doc, sync: vi.fn() });
    });
    (globalThis as any).Word = { run, InsertLocation: { replace: 'Replace' } };
    await insertDraftText('hello', 'live');
    expect(run).toHaveBeenCalledTimes(1);
  });

  it('inserts draft_text without replacing whole paragraph', async () => {
    const draft = 'draft_text';
    const range: any = {
      isEmpty: false,
      load: vi.fn(),
      text: 'orig',
      insertText: vi.fn((txt: string) => {
        range.text = txt;
        return {};
      }),
    };
    const body = { getRange: vi.fn() };
    const doc = { getSelection: () => range, body, comments: { add: vi.fn() } };
    const run = vi.fn(async (cb: any) => {
      await cb({ document: doc, sync: vi.fn() });
    });
    (globalThis as any).Word = { run, InsertLocation: { replace: 'Replace' } };
    await insertDraftText(draft, 'live');
    expect(range.insertText).toHaveBeenCalledWith(draft, 'Replace');
    expect(body.getRange).not.toHaveBeenCalled();
    expect(range.text).toBe(draft);
  });

  it('logs debug info and rethrows', async () => {
    const err: any = { code: 'X', message: 'boom', debugInfo: { errorLocation: 'loc' } };
    const run = vi.fn(async () => {
      throw err;
    });
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    (globalThis as any).Word = { run };
    await expect(insertDraftText('hi', 'live')).rejects.toBe(err);
    expect(spy).toHaveBeenCalledWith('insertDraftText error', err.code, err.message, err.debugInfo);
    spy.mockRestore();
  });
});
