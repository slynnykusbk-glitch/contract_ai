import { describe, it, expect, vi } from 'vitest';

describe('onInsertIntoWord', () => {
  it('inserts with CAI comment', async () => {
    (globalThis as any).__CAI_TESTING__ = true;
    const add = vi.fn();
    const sel = { isEmpty: false, load: vi.fn(), insertText: vi.fn().mockReturnValue({}) };
    const doc = { getSelection: () => sel, body: { getRange: () => ({}) }, comments: { add } } as any;
    const run = vi.fn(async (cb: any) => { await cb({ document: doc, sync: vi.fn() }); });
    (globalThis as any).Word = { run, InsertLocation: { replace: 'Replace' } };
    (globalThis as any).document = { querySelector: () => ({ value: 'draft' }) } as any;
    const mod = await import('../src/panel/index');
    await mod.onInsertIntoWord();
    expect(add).toHaveBeenCalled();
    const txt = add.mock.calls[0][1];
    expect(txt.startsWith('[CAI]')).toBe(true);
  });
});
