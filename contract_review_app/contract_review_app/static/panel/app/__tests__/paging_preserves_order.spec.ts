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

describe('renderResults paging', () => {
  beforeEach(() => {
    vi.resetModules();
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).__CAI_PAGE_SIZE__ = 2;
    setupDom('low');
  });

  it('preserves backend order when incrementally loading pages', async () => {
    const mod = await import('../assets/taskpane');
    const { renderResults } = mod;
    const findings = [
      { rule_id: 'A', severity: 'low', snippet: 'a' },
      { rule_id: 'B', severity: 'medium', snippet: 'b' },
      { rule_id: 'C', severity: 'medium', snippet: 'c' },
      { rule_id: 'D', severity: 'high', snippet: 'd' },
      { rule_id: 'E', severity: 'critical', snippet: 'e' },
    ];

    renderResults({ findings });

    const list = document.querySelectorAll('#findingsList li');
    const initialIds = Array.from(list).map(li => JSON.parse(li.textContent || '{}').rule_id);
    expect(initialIds).toEqual(['A', 'B']);

    const loadMore = document.getElementById('findingsLoadMore') as HTMLButtonElement;
    loadMore.click();

    const allItems = document.querySelectorAll('#findingsList li');
    const afterIds = Array.from(allItems).map(li => JSON.parse(li.textContent || '{}').rule_id);
    expect(afterIds).toEqual(['A', 'B', 'C', 'D', 'E']);
  });
});
