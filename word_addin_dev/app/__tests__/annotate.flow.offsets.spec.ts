import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

const anchorsMock = vi.fn();

vi.mock('../assets/anchors', () => ({
  findAnchors: anchorsMock
}));

describe('annotate flow offsets', () => {
  beforeEach(() => {
    vi.resetModules();
    anchorsMock.mockReset();
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } };
  });

  afterEach(() => {
    delete (globalThis as any).Word;
    delete (globalThis as any).Office;
    delete (globalThis as any).__lastAnalyzed;
    vi.restoreAllMocks();
  });

  it('requests anchors using nth derived from offsets', async () => {
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
    anchorsMock.mockImplementation(async (_body, _snippet, opts) => {
      expect(opts?.nth).toBe(2);
      return ranges;
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
      { rule_id: 'r1', snippet, start, end: start + snippet.length }
    ];

    const inserted = await annotateFindingsIntoWord(findings as any);
    expect(inserted).toBe(1);
    expect(insertedStarts).toEqual([targetRange.start]);
  });
});
