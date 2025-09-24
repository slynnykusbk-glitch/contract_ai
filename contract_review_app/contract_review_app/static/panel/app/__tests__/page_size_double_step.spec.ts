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

describe('renderResults page step', () => {
  beforeEach(() => {
    vi.resetModules();
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).__CAI_PAGE_SIZE__ = 2;
    setupDom('low');
  });

  it('increases findings limit by PAGE_SIZE * 2 on load more', async () => {
    const mod = await import('../assets/taskpane');
    const { renderResults } = mod;
    const findings = Array.from({ length: 10 }, (_, idx) => ({
      rule_id: `F${idx + 1}`,
      severity: 'medium',
      snippet: `s${idx + 1}`,
    }));

    renderResults({ findings });

    const list = document.getElementById('findingsList') as HTMLOListElement;
    expect(list.children.length).toBe(2);

    const loadMore = document.getElementById('findingsLoadMore') as HTMLButtonElement;
    loadMore.click();
    expect(list.children.length).toBe(6);

    loadMore.click();
    expect(list.children.length).toBe(10);
  });
});
