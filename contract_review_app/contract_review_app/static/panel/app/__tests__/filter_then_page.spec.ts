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

describe('renderResults filtering', () => {
  beforeEach(() => {
    vi.resetModules();
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).__CAI_PAGE_SIZE__ = 2;
    setupDom('high');
  });

  it('applies risk filter before pagination', async () => {
    const mod = await import('../assets/taskpane');
    const { renderResults } = mod;
    const findings = [
      { rule_id: 'LOW', severity: 'low', snippet: 'l' },
      { rule_id: 'MED', severity: 'medium', snippet: 'm' },
      { rule_id: 'HIGH1', severity: 'high', snippet: 'h1' },
      { rule_id: 'CRIT', severity: 'critical', snippet: 'c' },
      { rule_id: 'HIGH2', severity: 'high', snippet: 'h2' },
    ];

    renderResults({ findings });

    const items = document.querySelectorAll('#findingsList li');
    const ids = Array.from(items).map(li => JSON.parse(li.textContent || '{}').rule_id);
    expect(ids).toEqual(['HIGH1', 'CRIT']);
  });
});
