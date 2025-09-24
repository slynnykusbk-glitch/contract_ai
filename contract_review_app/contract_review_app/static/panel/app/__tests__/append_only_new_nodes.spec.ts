import { beforeEach, describe, expect, it, vi } from 'vitest';

const DOM_TEMPLATE = `
  <div id="resultsBlock"><div class="muted"></div></div>
  <div id="findingsBlock" style="display:none">
    <ol id="findingsList" data-role="findings"></ol>
  </div>
  <div id="recommendationsBlock" style="display:none">
    <ol id="recommendationsList" data-role="recommendations"></ol>
  </div>
  <span id="clauseTypeOut" data-role="clause-type"></span>
  <span id="resFindingsCount" data-role="findings-count"></span>
  <pre id="rawJson" data-role="raw-json"></pre>
  <button id="findingsLoadMore">Load more</button>
  <select id="selectRiskThreshold">
    <option value="low">low</option>
    <option value="medium">medium</option>
    <option value="high">high</option>
    <option value="critical">critical</option>
  </select>
`;

function setupDom(threshold: string) {
  document.body.innerHTML = DOM_TEMPLATE;
  const select = document.getElementById('selectRiskThreshold') as HTMLSelectElement;
  select.value = threshold;
}

describe('renderResults append flow', () => {
  beforeEach(() => {
    vi.resetModules();
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).__CAI_PAGE_SIZE__ = 2;
    setupDom('low');
  });

  it('appends only new nodes when loading more findings', async () => {
    const mod = await import('../assets/taskpane');
    const { renderResults } = mod;
    const findings = [
      { rule_id: 'A', severity: 'medium', snippet: 'a' },
      { rule_id: 'B', severity: 'medium', snippet: 'b' },
      { rule_id: 'C', severity: 'medium', snippet: 'c' },
      { rule_id: 'D', severity: 'medium', snippet: 'd' },
      { rule_id: 'E', severity: 'medium', snippet: 'e' },
    ];

    renderResults({ findings });

    const list = document.getElementById('findingsList') as HTMLOListElement;
    const initialNodes = Array.from(list.children);
    expect(initialNodes.length).toBe(2);

    const loadMore = document.getElementById('findingsLoadMore') as HTMLButtonElement;
    loadMore.click();

    const afterNodes = Array.from(list.children);
    expect(afterNodes.length).toBe(5);
    expect(initialNodes.every((node, idx) => node === afterNodes[idx])).toBe(true);
    const newNodes = afterNodes.slice(initialNodes.length);
    expect(newNodes.length).toBe(3);
    newNodes.forEach(node => {
      expect(initialNodes).not.toContain(node);
    });
  });
});
