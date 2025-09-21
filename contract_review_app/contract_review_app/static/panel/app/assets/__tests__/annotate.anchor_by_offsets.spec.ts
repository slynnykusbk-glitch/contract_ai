import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const searchNthMock = vi.fn();
const findAnchorsMock = vi.fn();
let annotateMod: Awaited<typeof import('../annotate.ts')>;
let annotateFindingsIntoWord: (typeof import('../annotate.ts'))['annotateFindingsIntoWord'];

vi.mock('../anchors.ts', async () => {
  const actual = await vi.importActual<typeof import('../anchors.ts')>('../anchors.ts');
  return {
    ...actual,
    searchNth: searchNthMock,
    findAnchors: findAnchorsMock
  };
});

describe('annotate anchor by offsets', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    searchNthMock.mockReset();
    findAnchorsMock.mockReset();
    (globalThis as any).__lastAnalyzed = '';
    (globalThis as any).document = { getElementById: () => null };
    annotateMod = await import('../annotate.ts');
    annotateFindingsIntoWord = annotateMod.annotateFindingsIntoWord;
  });

  afterEach(() => {
    delete (globalThis as any).Word;
    delete (globalThis as any).__lastAnalyzed;
    delete (globalThis as any).document;
    vi.restoreAllMocks();
  });

  it('priority: nth -> normalized -> token -> cc', async () => {
    const safeInsertSpy = vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: true } as any);
    const fallbackSpy = vi
      .spyOn(annotateMod, 'fallbackAnnotateWithContentControl')
      .mockResolvedValue({ ok: true });

    const calls: string[] = [];
    const range = {
      start: 0,
      end: 20,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertComment: vi.fn(),
      insertContentControl: () => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn()
      })
    } as any;

    const token = 'Supercalifragilistic';
    const rawSnippet = 'Quote — “' + token + '”';
    const normalizedSnippet = 'Quote - "' + token + '"';

    searchNthMock.mockImplementation(async (_body, needle) => {
      calls.push(needle);
      if (needle === token) return range;
      return null;
    });

    findAnchorsMock.mockResolvedValue([]);

    (globalThis as any).__lastAnalyzed = rawSnippet;

    const ccRangeStub = () => ({
      context: { sync: vi.fn(async () => {}) },
      insertContentControl: () => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn()
      })
    });

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => ccRangeStub())
        }
      },
      sync: vi.fn(async () => {})
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx)
    };

    const findings = [
      { rule_id: 'r1', snippet: rawSnippet, start: 0, end: rawSnippet.length }
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
    expect(calls[0]).toBe(rawSnippet);
    expect(calls[1]).toBe(normalizedSnippet);
    expect(calls[2]).toBe(token);
    expect(fallbackSpy).not.toHaveBeenCalled();
  });

  it('normalized fallback handles mixed quotes and dashes', async () => {
    vi.spyOn(annotateMod, 'safeInsertComment').mockResolvedValue({ ok: true } as any);
    vi.spyOn(annotateMod, 'fallbackAnnotateWithContentControl').mockResolvedValue({ ok: false });

    const normalizedNeedle = 'alpha - "beta"';
    const rawSnippet = 'alpha — “beta”';
    const expectedRange = {
      start: 5,
      end: 15,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertComment: vi.fn(),
      insertContentControl: () => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn()
      })
    } as any;

    searchNthMock.mockImplementation(async (_body, needle) => {
      if (needle === rawSnippet) return null;
      if (needle === normalizedNeedle) return expectedRange;
      return null;
    });

    findAnchorsMock.mockResolvedValue([]);

    (globalThis as any).__lastAnalyzed = rawSnippet;

    const ccRangeStub = () => ({
      context: { sync: vi.fn(async () => {}) },
      insertContentControl: () => ({
        tag: '',
        title: '',
        color: '',
        insertText: vi.fn()
      })
    });

    const ctx = {
      document: {
        body: {
          context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } },
          getRange: vi.fn(() => ccRangeStub())
        }
      },
      sync: vi.fn(async () => {})
    } as any;

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => cb(ctx)
    };

    const findings = [
      { rule_id: 'r2', snippet: rawSnippet, start: 0, end: rawSnippet.length }
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
    expect(searchNthMock).toHaveBeenCalledWith(expect.anything(), normalizedNeedle, expect.any(Number), expect.any(Object));
  });
});
