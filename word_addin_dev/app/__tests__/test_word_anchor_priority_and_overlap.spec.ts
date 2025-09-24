import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';

const anchorByOffsetsMock = vi.fn();
const findAnchorsMock = vi.fn();

vi.mock('../assets/anchors', async () => {
  const actual = await vi.importActual<typeof import('../assets/anchors')>('../assets/anchors');
  return {
    ...actual,
    anchorByOffsets: anchorByOffsetsMock,
    findAnchors: findAnchorsMock,
  };
});

describe('annotateFindingsIntoWord anchor priority', () => {
  const originalWord = (globalThis as any).Word;
  const originalDocument = (globalThis as any).document;
  const originalWindow = (globalThis as any).window;
  const originalHTMLElement = (globalThis as any).HTMLElement;
  const originalNode = (globalThis as any).Node;
  const originalTestingFlag = (globalThis as any).__CAI_TESTING__;
  const originalLastAnalyzed = (globalThis as any).__lastAnalyzed;
  let dom: JSDOM | null = null;

  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    anchorByOffsetsMock.mockReset();
    findAnchorsMock.mockReset();
    dom = new JSDOM(`<!doctype html><html><body><input id="cai-dry-run-annotate" type="checkbox" /></body></html>`);
    (globalThis as any).window = dom.window as any;
    (globalThis as any).document = dom.window.document as any;
    (globalThis as any).HTMLElement = dom.window.HTMLElement;
    (globalThis as any).Node = dom.window.Node;
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).__lastAnalyzed = 'alpha beta beta overlap gamma';
  });

  afterEach(() => {
    if (dom) {
      dom.window.close();
    }
    dom = null;
    if (originalWord === undefined) delete (globalThis as any).Word;
    else (globalThis as any).Word = originalWord;
    if (originalDocument === undefined) delete (globalThis as any).document;
    else (globalThis as any).document = originalDocument;
    if (originalWindow === undefined) delete (globalThis as any).window;
    else (globalThis as any).window = originalWindow;
    if (originalHTMLElement === undefined) delete (globalThis as any).HTMLElement;
    else (globalThis as any).HTMLElement = originalHTMLElement;
    if (originalNode === undefined) delete (globalThis as any).Node;
    else (globalThis as any).Node = originalNode;
    if (originalTestingFlag === undefined) delete (globalThis as any).__CAI_TESTING__;
    else (globalThis as any).__CAI_TESTING__ = originalTestingFlag;
    if (originalLastAnalyzed === undefined) delete (globalThis as any).__lastAnalyzed;
    else (globalThis as any).__lastAnalyzed = originalLastAnalyzed;
  });

  it('prefers offset anchors, falls back to search, and skips overlaps', async () => {
    const annotateMod = await import('../assets/annotate');

    const added: Array<{ start: number; end: number; text: string }> = [];
    const makeRange = (start: number, end: number) => {
      const add = vi.fn((_range: any, text: string) => {
        added.push({ start, end, text });
      });
      return {
        start,
        end,
        load: vi.fn(),
        context: {
          document: { comments: { add } },
          sync: vi.fn(async () => {}),
        },
        insertContentControl: vi.fn(() => {
          added.push({ start, end, text: '[cc]' });
          return {
            tag: '',
            title: '',
            color: '',
            insertText: vi.fn(),
          };
        }),
      };
    };

    const rangeA = makeRange(0, 5);
    const rangeB = makeRange(10, 16);
    const rangeC = makeRange(12, 20);

    anchorByOffsetsMock
      .mockResolvedValueOnce(rangeA)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(rangeC);
    findAnchorsMock.mockResolvedValueOnce([rangeB]);

    const body = { context: { sync: vi.fn(async () => {}), trackedObjects: { add: vi.fn() } } };
    const ctx = {
      document: { body },
      sync: vi.fn(async () => {}),
    };

    (globalThis as any).Word = {
      InsertLocation: { end: 'end' },
      run: async (cb: any) => await cb(ctx),
    };

    const findings = [
      { rule_id: 'F1', snippet: 'alpha', start: 0, end: 5, severity: 'high' },
      { rule_id: 'F2', snippet: 'beta', start: 10, end: 16, severity: 'medium' },
      { rule_id: 'F3', snippet: 'beta overlap', start: 12, end: 20, severity: 'medium' },
    ];

    const inserted = await annotateMod.annotateFindingsIntoWord(findings as any);

    expect(inserted).toBe(2);
    expect(anchorByOffsetsMock).toHaveBeenCalledTimes(2);
    expect(findAnchorsMock).toHaveBeenCalledTimes(1);
    expect(added).toHaveLength(2);
    expect(added[0].start).toBe(0);
    expect(added[1].start).toBe(10);
    expect(added.find(entry => entry.start === 12)).toBeUndefined();
  });
});
