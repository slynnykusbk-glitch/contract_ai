import { describe, it, expect, vi } from 'vitest';
import { fallbackAnnotateWithContentControl } from '../annotate.ts';

;(globalThis as any).Word = { InsertLocation: { end: 'end' } } as any;

describe('fallbackAnnotateWithContentControl', () => {
  it('skips when content control already exists', async () => {
    const range: any = {
      context: { sync: vi.fn().mockResolvedValue(undefined) },
      load: vi.fn(),
      parentContentControl: { tag: 'cai-note' }
    };
    const res = await fallbackAnnotateWithContentControl(range, 'hi');
    expect(res.ok).toBe(false);
    expect(range.load).toHaveBeenCalledWith('parentContentControl');
  });

  it('inserts new content control when missing', async () => {
    const cc: any = { insertText: vi.fn() };
    const range: any = {
      context: { sync: vi.fn().mockResolvedValue(undefined) },
      load: vi.fn(),
      insertContentControl: vi.fn(() => cc)
    };
    const res = await fallbackAnnotateWithContentControl(range, 'note');
    expect(res.ok).toBe(true);
    expect(range.insertContentControl).toHaveBeenCalled();
    expect(cc.tag).toBe('cai-note');
    expect(cc.title).toBe('ContractAI Note');
    expect(cc.insertText).toHaveBeenCalledWith('CAI: note', Word.InsertLocation.end);
  });
});
