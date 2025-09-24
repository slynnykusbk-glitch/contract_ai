import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';

describe('QA merge deduplication', () => {
  const originalWindow = globalThis.window;
  const originalDocument = globalThis.document;
  const originalHTMLElement = (globalThis as any).HTMLElement;
  const originalNode = (globalThis as any).Node;
  const originalLocalStorage = (globalThis as any).localStorage;
  const originalLocation = (globalThis as any).location;
  const originalTestingFlag = (globalThis as any).__CAI_TESTING__;
  let dom: JSDOM | null = null;

  beforeEach(() => {
    vi.resetModules();
    const html = `
      <section id="resultsBlock">
        <div class="muted">Results</div>
      </section>
    `;
    dom = new JSDOM(`<!doctype html><html><body>${html}</body></html>`, { url: 'https://panel.test' });
    (globalThis as any).window = dom.window as any;
    (globalThis as any).document = dom.window.document as any;
    (globalThis as any).HTMLElement = dom.window.HTMLElement;
    (globalThis as any).Node = dom.window.Node;
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).localStorage = {
      getItem: () => null,
      setItem: () => {},
    };
    (globalThis as any).location = dom.window.location;
  });

  afterEach(() => {
    if (dom) {
      dom.window.close();
    }
    dom = null;
    if (originalWindow === undefined) delete (globalThis as any).window;
    else globalThis.window = originalWindow;
    if (originalDocument === undefined) delete (globalThis as any).document;
    else globalThis.document = originalDocument;
    if (originalHTMLElement === undefined) delete (globalThis as any).HTMLElement;
    else (globalThis as any).HTMLElement = originalHTMLElement;
    if (originalNode === undefined) delete (globalThis as any).Node;
    else (globalThis as any).Node = originalNode;
    if (originalLocalStorage === undefined) delete (globalThis as any).localStorage;
    else (globalThis as any).localStorage = originalLocalStorage;
    if (originalLocation === undefined) delete (globalThis as any).location;
    else (globalThis as any).location = originalLocation;
    if (originalTestingFlag === undefined) delete (globalThis as any).__CAI_TESTING__;
    else (globalThis as any).__CAI_TESTING__ = originalTestingFlag;
    delete (globalThis as any).__findings;
  });

  it('removes duplicates and keeps highest severity entries', async () => {
    const mod = await import('../assets/taskpane');
    const base = [
      { rule_id: 'R1', snippet: 'First clause', start: 0, end: 12, severity: 'high' },
      { rule_id: 'R2', snippet: 'Second clause', start: 20, end: 35, severity: 'medium' },
      { rule_id: 'R3', snippet: 'Third clause', start: 40, end: 55, severity: 'medium' },
      { rule_id: 'R4', snippet: 'Fourth clause', start: 60, end: 75, severity: 'low' },
      { rule_id: 'R5', snippet: 'Fifth clause', start: 80, end: 96, severity: 'high' },
    ];
    (globalThis as any).__findings = base;
    if (dom) {
      (dom.window as any).__findings = base;
    }

    const qa = [
      { rule_id: 'R2', snippet: 'Second clause', start: 20, end: 35, severity: 'critical' },
      { rule_id: 'R6', snippet: 'Sixth clause', start: 100, end: 118, severity: 'medium' },
      { rule_id: 'R3', snippet: 'Third clause', start: 40, end: 55, severity: 'high' },
      { rule_id: 'R2', snippet: 'Second clause', start: 20, end: 35, severity: 'low' },
    ];

    const merged = mod.mergeQaResultsForTests({ findings: qa });
    expect(Array.isArray(merged.findings)).toBe(true);
    expect(merged.findings).toHaveLength(6);

    const r2Entries = merged.findings.filter((f: any) => f.rule_id === 'R2');
    expect(r2Entries).toHaveLength(1);
    expect(r2Entries[0].severity).toBe('critical');

    const r3Entries = merged.findings.filter((f: any) => f.rule_id === 'R3');
    expect(r3Entries).toHaveLength(1);
    expect(r3Entries[0].severity).toBe('high');

    const codes = merged.findings.map((f: any) => f.rule_id);
    expect(codes).toContain('R6');
  });
});
