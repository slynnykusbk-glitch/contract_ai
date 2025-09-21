import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const anchorsMock = vi.fn();
const searchNthMock = vi.fn();
const anchorByOffsetsMock = vi.fn();

vi.mock('../assets/anchors', async () => {
  const actual = await vi.importActual<typeof import('../assets/anchors')>('../assets/anchors');
  return {
    ...actual,
    anchorByOffsets: anchorByOffsetsMock,
    findAnchors: anchorsMock,
    searchNth: searchNthMock
  };
});

describe('annotate flow offsets', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    anchorsMock.mockReset();
    searchNthMock.mockReset();
    anchorByOffsetsMock.mockReset();
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } };
  });

  afterEach(() => {
    delete (globalThis as any).Word;
    delete (globalThis as any).Office;
    delete (globalThis as any).__lastAnalyzed;
    vi.restoreAllMocks();
  });

  it('requests anchors using nth derived from offsets', async () => {
    anchorByOffsetsMock.mockImplementation(async opts => {
      return (await searchNthMock(opts.body, opts.snippet, opts.nth ?? 0, opts.searchOptions)) as any;
    });
    const baseText = 'foo bar foo bar foo bar foo bar';
    (globalThis as any).__lastAnalyzed = baseText;
    const snippet = 'foo bar';
    const starts: number[] = [];
    let idx = -1;
    while ((idx = baseText.indexOf(snippet, idx + 1)) !== -1) {
      starts.push(idx);
    }
    const start = starts[2];

    const targetRange = { start, end: start + snippet.length, load: vi.fn() } as any;
    const otherRanges = [
      { start: starts[0], end: starts[0] + snippet.length, load: vi.fn() },
      { start: starts[1], end: starts[1] + snippet.length, load: vi.fn() }
    ];

    const annotateMod = await import('../assets/annotate');
    const { annotateFindingsIntoWord } = annotateMod;

    const insertedStarts: number[] = [];
    const wrapRange = (range: any) => ({
      ...range,
      context: { sync: vi.fn(async () => {}), document: {} },
      parentContentControl: null,
      insertContentControl: () => {
        insertedStarts.push(range.start);
        return {
          tag: '',
          title: '',
          color: '',
          insertText: vi.fn()
        };
      }
    });

    const ranges = [...otherRanges.map(wrapRange), wrapRange(targetRange)];
    searchNthMock.mockImplementation(async (_body, needle, nth) => {
      expect(needle).toBe(snippet);
      expect(nth).toBe(2);
      return ranges.find(r => r.start === targetRange.start) as any;
    });

    anchorsMock.mockResolvedValue([]);

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => {
        const ctx = {
          document: {
            body: {
              context: { sync: vi.fn(async () => {}), trackedObjects: { add: () => {} } }
            }
          },
          sync: vi.fn(async () => {})
        };
        return await cb(ctx);
      }
    };
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => false } } };

    const findings = [
      { rule_id: 'r1', snippet, start, end: start + snippet.length }
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
    expect(insertedStarts).toEqual([targetRange.start]);
    expect(searchNthMock).toHaveBeenCalled();
  });

  it('uses the first reordered anchor when offset anchoring fails', async () => {
    anchorByOffsetsMock.mockResolvedValue(null);
    const baseText = 'foo bar foo bar foo bar foo bar';
    (globalThis as any).__lastAnalyzed = baseText;
    const snippet = 'foo bar';

    const starts: number[] = [];
    let idx = -1;
    while ((idx = baseText.indexOf(snippet, idx + 1)) !== -1) {
      starts.push(idx);
    }

    const insertedStarts: number[] = [];

    const makeRange = (start: number) => ({
      start,
      end: start + snippet.length,
      load: vi.fn(),
      context: { sync: vi.fn(async () => {}) },
      insertContentControl: () => {
        insertedStarts.push(start);
        return {
          tag: '',
          title: '',
          color: '',
          insertText: vi.fn()
        };
      }
    });

    const preferredRange = makeRange(starts[2]);

    const otherRanges = [starts[0], starts[1]].map(makeRange) as any[];

    const annotateMod = await import('../assets/annotate');
    const { annotateFindingsIntoWord } = annotateMod;

    searchNthMock.mockResolvedValue(null);
    anchorsMock.mockImplementation(async (_body, text, opts) => {
      expect(text).toBe(snippet);
      expect(opts?.nth).toBe(2);
      return [preferredRange, ...otherRanges];
    });

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => {
        const ctx = {
          document: {
            body: {
              context: { sync: vi.fn(async () => {}), trackedObjects: { add: () => {} } }
            }
          },
          sync: vi.fn(async () => {})
        };
        return await cb(ctx);
      }
    };

    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => false } } };

    const findings = [
      { rule_id: 'r1', snippet, start: preferredRange.start, end: preferredRange.end, nth: 2 }
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
    expect(insertedStarts).toEqual([preferredRange.start]);
    expect(preferredRange.load).toHaveBeenCalledWith(['start', 'end']);
    expect(anchorsMock).toHaveBeenCalledWith(expect.anything(), snippet, { nth: 2 });
  });

  it('keeps findings ordered by offsets and skips overlaps while preserving offsets', async () => {
    const baseText = 'alpha beta gamma delta epsilon zeta';
    (globalThis as any).__lastAnalyzed = baseText;

    const annotateMod = await import('../assets/annotate');
    const { planAnnotations } = annotateMod;

    const findings = [
      { rule_id: 'r1', snippet: 'alpha', start: 0, end: 5, nth: 0 },
      { rule_id: 'r2', snippet: 'beta', start: 4, end: 8 },
      { rule_id: 'r3', snippet: 'delta', start: baseText.indexOf('delta'), end: baseText.indexOf('delta') + 'delta'.length }
    ];

    const plan = planAnnotations(findings as any);

    expect(plan.map(p => p.rule_id)).toEqual(['r1', 'r3']);
    expect(plan[0]).toMatchObject({ start: 0, end: 5, nth: 0 });
    expect(plan[1]).toMatchObject({ start: findings[2].start, end: findings[2].end });
  });
});
