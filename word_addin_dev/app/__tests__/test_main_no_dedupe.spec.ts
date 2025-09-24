import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';

describe('main findings list preserves backend ordering', () => {
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
      <div id="findingsBlock" style="display: none"></div>
      <ol id="findingsList" data-role="findings"></ol>
      <div id="recommendationsBlock" style="display: none"></div>
      <ol id="recommendationsList" data-role="recommendations"></ol>
      <span id="resClauseType" data-role="clause-type"></span>
      <span id="resFindingsCount" data-role="findings-count"></span>
      <pre id="rawJson" data-role="raw-json"></pre>
    `;
    dom = new JSDOM(`<!doctype html><html><body>${html}</body></html>`, {
      url: 'https://panel.test',
    });
    globalThis.window = dom.window as any;
    globalThis.document = dom.window.document as any;
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
    if (originalWindow === undefined) {
      delete (globalThis as any).window;
    } else {
      globalThis.window = originalWindow;
    }
    if (originalDocument === undefined) {
      delete (globalThis as any).document;
    } else {
      globalThis.document = originalDocument;
    }
    if (originalHTMLElement === undefined) {
      delete (globalThis as any).HTMLElement;
    } else {
      (globalThis as any).HTMLElement = originalHTMLElement;
    }
    if (originalNode === undefined) {
      delete (globalThis as any).Node;
    } else {
      (globalThis as any).Node = originalNode;
    }
    if (originalLocalStorage === undefined) {
      delete (globalThis as any).localStorage;
    } else {
      (globalThis as any).localStorage = originalLocalStorage;
    }
    if (originalLocation === undefined) {
      delete (globalThis as any).location;
    } else {
      (globalThis as any).location = originalLocation;
    }
    if (originalTestingFlag === undefined) {
      delete (globalThis as any).__CAI_TESTING__;
    } else {
      (globalThis as any).__CAI_TESTING__ = originalTestingFlag;
    }
    delete (globalThis as any).__findings;
  });

  it('renders duplicates without reordering', async () => {
    const mod = await import('../assets/taskpane');
    const findings = [
      { rule_id: 'R3', snippet: 'Clause three', start: 30, end: 40, severity: 'critical' },
      { rule_id: 'R1', snippet: 'Clause one', start: 0, end: 10, severity: 'high' },
      { rule_id: 'R1', snippet: 'Clause one', start: 0, end: 10, severity: 'medium' },
      { rule_id: 'R2', snippet: 'Clause two', start: 20, end: 28, severity: 'medium' },
    ];

    mod.renderResults({
      analysis: { findings },
      clause_type: 'Test',
    });

    const items = Array.from(document.querySelectorAll('#findingsList li'));
    expect(items).toHaveLength(4);
    const order = items.map(li => {
      const txt = li.textContent || '{}';
      try {
        const parsed = JSON.parse(txt);
        return parsed.rule_id;
      } catch {
        return txt;
      }
    });
    expect(order).toEqual(['R3', 'R1', 'R1', 'R2']);
  });
});
